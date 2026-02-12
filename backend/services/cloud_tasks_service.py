from google.cloud import tasks_v2
from utils.env import settings
import json

class CloudTasksService:
    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.queue_path = self.client.queue_path(
            settings.GOOGLE_CLOUD_PROJECT,
            settings.CLOUD_TASKS_LOCATION,
            settings.CLOUD_TASKS_QUEUE
        )

    def enqueue_video_job(self, job_id: str, job_data: dict) -> str:
        """Enqueue a video generation job to Cloud Tasks"""
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.WORKER_SERVICE_URL}/worker/process",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "job_id": job_id,
                    **job_data
                }).encode(),
            }
        }

        response = self.client.create_task(parent=self.queue_path, task=task)
        return response.name

