Install the application and testing requirements:
```bash
# Install main API dependencies
pip install -r requirements.txt
# Install the shared library
pip install ../shared
# Install testing tools
pip install -r tests/requirements.txt
```

Run the test suite:
```bash
PYTHONPATH=. pytest tests/unit/
```

### Note on `.venv`
You can keep the `.venv` directory; it's a standard way to manage isolated dependencies for this project. If you want to save space and don't plan on running tests again soon, you can delete it with `rm -rf .venv`.

