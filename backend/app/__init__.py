"""
Application factory for Feinschmecker API.

This module provides the Flask application factory pattern for creating
and configuring the API application with proper extensions and blueprints.
"""
import os
from pathlib import Path

import logging
import uuid
import time
from flask import Flask, request, g
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger, swag_from
from owlready2 import get_ontology, default_world
from owlready2.base import OwlReadyOntologyParsingError

from backend.config import get_config


# Initialize extensions
cache = Cache()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[]
)

# Global ontology instance
onto = None


def setup_logging(app):
    """Configure application logging."""
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=app.config['LOG_FORMAT'],
        datefmt=app.config['LOG_DATE_FORMAT']
    )
    
    # Set Flask logger level
    app.logger.setLevel(log_level)


def load_ontology(app):
    """Load the ontology at application startup."""
    global onto

    ontology_path = app.config.get('ONTOLOGY_URL')
    if not ontology_path:
        app.logger.info("ONTOLOGY_URL not set, using default 'data/feinschmecker.nt'")
        ontology_path = 'data/feinschmecker.nt'

    try:
        # If it's an HTTP(S) URL, download it into a local cache and load from there.
        if ontology_path.startswith('http://') or ontology_path.startswith('https://'):
            # Prepare cache directory
            cache_dir = Path(app.config.get('ONTOLOGY_CACHE_DIR', '/tmp/owlready2_cache'))
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Determine filename: prefer explicitly configured filename (should be .rdf),
            # otherwise derive from the URL path and force .rdf extension.
            fname = app.config.get('ONTOLOGY_CACHE_FILENAME')
            if not fname:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(ontology_path)
                    fname = Path(parsed.path).name or 'feinschmecker.rdf'
                except Exception:
                    fname = 'feinschmecker.rdf'

            # Ensure .rdf extension for compatibility with Owlready2
            if not Path(fname).suffix.lower() == '.rdf':
                fname = Path(fname).with_suffix('.rdf').name

            absolute_path = (cache_dir / fname).resolve()

            # Download the remote ontology to local cache (stream and atomically replace)
            try:
                from urllib.request import urlopen
                import os

                app.logger.info(f"Downloading ontology from {ontology_path} to {absolute_path}")
                resp = urlopen(ontology_path, timeout=60)

                tmp_path = absolute_path.with_suffix(absolute_path.suffix + '.part')
                try:
                    with tmp_path.open('wb') as fh:
                        chunk_size = 8192
                        while True:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            fh.write(chunk)

                    # atomic replace to avoid partial-read by workers
                    if tmp_path.exists():
                        try:
                            os.replace(str(tmp_path), str(absolute_path))
                            app.logger.info(f"Downloaded ontology to {absolute_path} (atomic)")
                        except FileNotFoundError as fnf:
                            app.logger.error(f"Atomic replace failed — part file missing: {fnf}")
                            # If absolute already exists, continue using it; otherwise surface error
                            if not absolute_path.exists():
                                raise
                        except Exception:
                            app.logger.exception('Failed to atomically replace ontology file')
                            if not absolute_path.exists():
                                raise
                    else:
                        app.logger.error(f"Temporary download file not found: {tmp_path}")
                        if not absolute_path.exists():
                            raise FileNotFoundError(f"Download produced no temporary file and no cached file exists: {absolute_path}")
                finally:
                    if tmp_path.exists():
                        try:
                            tmp_path.unlink()
                        except Exception:
                            pass
            except Exception as ex:
                app.logger.exception(f"Failed to download ontology from {ontology_path}: {ex}")
                # If download failed but a cached file exists, continue using it
                if not absolute_path.exists():
                    raise

            ontology_uri = absolute_path.as_uri()

        else:
            # app.root_path is backend/app, so project root is two levels up.
            project_root = Path(app.root_path).parent.parent
            absolute_path = (project_root / ontology_path).resolve()
            if not absolute_path.exists():
                app.logger.error(f"Ontology file not found at resolved path: {absolute_path}")
                raise FileNotFoundError(f"Ontology file not found: {absolute_path}")
            ontology_uri = absolute_path.as_uri()

        # Save local path into config so other parts of the app can persist updates
        try:
            app.config['ONTOLOGY_LOCAL_PATH'] = str(absolute_path)
        except Exception:
            app.logger.exception('Failed to set ONTOLOGY_LOCAL_PATH')

        app.logger.info(f"Loading ontology from {ontology_uri}")

        # Try to load ontology with a few retries — this helps if workers race and
        # a file replace overlaps parsing attempts (transient partial reads).
        max_retries = int(app.config.get('ONTOLOGY_LOAD_RETRIES', 3))
        retry_delay = float(app.config.get('ONTOLOGY_LOAD_RETRY_DELAY', 2.0))
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                onto = get_ontology(ontology_uri).load()
                app.logger.info("Ontology loaded successfully")
                last_exc = None
                break
            except OwlReadyOntologyParsingError as oe:
                last_exc = oe
                app.logger.warning(f"Ontology parse failed (attempt {attempt}/{max_retries}): {oe}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    raise
            except Exception as ex:
                last_exc = ex
                app.logger.exception(f"Unexpected error while loading ontology (attempt {attempt}/{max_retries}): {ex}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    raise

        # Notify workers about the loaded ontology by writing the
        # ontology source URI (original URL if remote, or file URI) and a version token into Redis.
        try:
            import os
            import redis as _redis
            redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
            r = _redis.from_url(redis_url)
            # If the configured ONTOLOGY_URL was remote, publish that original HTTP(S) URL
            # so workers load from the authoritative source. Otherwise publish the
            # local file URI.
            source_uri = ontology_path if (isinstance(ontology_path, str) and (ontology_path.startswith('http://') or ontology_path.startswith('https://'))) else ontology_uri
            r.set('feinschmecker:ontology_uri', source_uri)
            # Use a monotonically increasing version token (timestamp)
            r.set('feinschmecker:ontology_version', str(int(__import__('time').time())))
            app.logger.info("Published ontology_uri and ontology_version to Redis for workers")
        except Exception:
            app.logger.exception("Failed to publish ontology version to Redis")

        return onto
    except Exception as e:
        # Don't crash the entire WSGI process if Owlready2 fails to parse the RDF/XML.
        # Instead, capture diagnostic information, persist a copy for inspection,
        # surface a config flag so other parts of the app know the ontology isn't loaded,
        # and allow the app to continue running in a degraded mode.
        app.logger.error(f"Failed to load ontology from {ontology_path}: {str(e)}", exc_info=True)

        # Mark that loading failed so callers can detect degraded mode
        try:
            app.config['ONTOLOGY_LOAD_ERROR'] = True
        except Exception:
            pass

        # Attempt to capture first lines of the cached file for quicker debugging
        try:
            if 'absolute_path' in locals() and absolute_path.exists():
                # Read a bounded portion to avoid huge logs
                text = absolute_path.read_text(errors='replace')
                head_lines = text.splitlines()[:80]
                app.logger.error('--- Begin cached RDF head (first 80 lines) ---')
                for i, ln in enumerate(head_lines, start=1):
                    app.logger.error(f"{i:04d}: {ln}")
                app.logger.error('--- End cached RDF head ---')

                # Save a diagnostic copy into the Flask instance folder for easier retrieval
                try:
                    diag_dir = Path(app.instance_path)
                    diag_dir.mkdir(parents=True, exist_ok=True)
                    diag_file = diag_dir / f"feinschmecker_failed_{int(__import__('time').time())}.rdf"
                    diag_file.write_text(text, errors='replace')
                    app.logger.error(f"Saved diagnostic copy to {diag_file}")
                except Exception:
                    app.logger.exception('Failed to write diagnostic copy of cached RDF')
        except Exception:
            app.logger.exception('Failed to read cached ontology file for diagnostics')

        # Ensure global onto remains None, and return gracefully
        onto = None
        return None


def create_app(config_name=None):
    """
    Application factory for creating Flask app instances.
    
    Args:
        config_name: Configuration environment name ('development', 'production', 'testing')
                    If None, uses FLASK_ENV environment variable
    
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Setup logging and record factory first (before any logging calls)
    setup_logging(app)
    
    # Inject request ID into log records
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            # Try to get request_id from Flask's g object
            record.request_id = getattr(g, 'request_id', 'N/A')
        except RuntimeError:
            # Outside of request context (e.g., during app initialization)
            record.request_id = 'INIT'
        return record
    
    logging.setLogRecordFactory(record_factory)
    
    # Initialize extensions
    CORS(app, 
         origins=app.config['CORS_ORIGINS'],
         methods=app.config['CORS_METHODS'],
         allow_headers=app.config['CORS_ALLOW_HEADERS'])
    
    cache.init_app(app)
    
    if app.config['RATELIMIT_ENABLED']:
        limiter.init_app(app)
        app.logger.info(f"Rate limiting enabled: {app.config['RATELIMIT_DEFAULT']}")
    
    # Initialize Swagger
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    }
    
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Feinschmecker API",
            "description": "RESTful API for querying recipe data from an OWL/RDF knowledge graph. "
                         "Supports advanced filtering by nutritional values, dietary restrictions, "
                         "ingredients, cooking time, and difficulty level.",
            "version": app.config['API_VERSION'],
            "contact": {
                "name": "Feinschmecker Team"
            }
        },
        "host": "127.0.0.1:5000",
        "basePath": "/",
        "schemes": ["http"],
        "consumes": ["application/json"],
        "produces": ["application/json"]
    }
    
    Swagger(app, config=swagger_config, template=swagger_template)
    app.logger.info("Swagger documentation initialized at /apidocs/")
    
    # Load ontology
    with app.app_context():
        load_ontology(app)
    
    # Request ID middleware
    @app.before_request
    def before_request():
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    
    # Register blueprints
    from backend.app.api import api_bp
    app.register_blueprint(api_bp)
    
    # Root endpoint
    @app.route('/')
    @swag_from('api/swagger_specs/index.yml')
    def index():
        return {
            'message': 'Welcome to the Feinschmecker API!',
            'version': app.config['API_VERSION'],
            'endpoints': {
                'recipes': '/recipes'
            }
        }
    
    app.logger.info(f"Feinschmecker API initialized in {config_name or 'default'} mode")
    
    return app


def get_ontology_instance():
    """
    Get the loaded ontology instance.
    
    Returns:
        The loaded ontology object
    """
    return onto
