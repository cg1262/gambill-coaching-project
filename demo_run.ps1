cd E:\gde_git\ai-data-modeling-ide\apps\api
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000