from fastapi import APIRouter

from engine.argo_engine import ArgoEngine

router = APIRouter()

#submit argo workflow 
@router.post("/submit")
def submit_workflow():
    #authenticate()
    #ArgoEngine.submit_workflow({})
    return {"message": "submit"}

    

#get status
@router.get("/status/{workflow_name}")
def get_workflow_status(workflow_name: str):
    #is_authorized = authenticate()
    #if not is_authorized:
    #    raise HTTPException(status_code=404, detail="user not authorized access to workflow status")
    #ArgoEngine.get_workflow_status(workflow_name)
    return {"message": "status"}
    

    
#cancel workflow 
@router.post("/cancel/{workflow_name}")
def cancel_workflow(workflow_name: str):
    #authenticate()
    #ArgoEngine.cancel_workflow(workflow_name)
    return {"message": "cancel"}

def init_app(app):
    app.include_router(router)