from fastapi import FastAPI
from fastapi.testclient import TestClient

# import your router
from ai_feedback import router as ai_feedback_router

# set up a dummy app just for testing ai_feedback.py
app = FastAPI()
app.include_router(ai_feedback_router)

client = TestClient(app)

def test_insights_route():
    # replace student_id=1 with a dummy one, it will probably 404 but at least confirms routing works
    response = client.get("/insights/1")
    print("Status:", response.status_code)
    print("Body:", response.text)

if __name__ == "__main__":
    test_insights_route()
