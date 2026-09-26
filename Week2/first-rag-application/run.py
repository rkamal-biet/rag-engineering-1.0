"""
Start the API server:

    python run.py

Then open http://127.0.0.1:8000/docs (Swagger UI).
"""

import uvicorn

if __name__ == "__main__":
    # reload=True restarts the server when you edit a file under app/
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=["app"])
