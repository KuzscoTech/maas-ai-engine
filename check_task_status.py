#!/usr/bin/env python3
"""
Quick script to check if the task was completed in the platform database
"""

import requests
import json

TEST_USER = {"email": "admin@example.com", "password": "admin123"}
PLATFORM_URL = "http://localhost:8000"

def check_task_status():
    # Get token
    login_response = requests.post(f"{PLATFORM_URL}/api/v1/auth/login", json=TEST_USER)
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check the latest task
    task_id = "custom_f1aae195_20250616_044933"
    
    response = requests.get(f"{PLATFORM_URL}/api/v1/tasks/{task_id}", headers=headers)
    
    if response.status_code == 200:
        task_data = response.json()
        print(f"✅ Task: {task_id}")
        print(f"   Status: {task_data.get('status')}")
        print(f"   Metadata: {json.dumps(task_data.get('metadata'), indent=2)}")
        print(f"   Results: {json.dumps(task_data.get('results'), indent=2)}")
        print(f"   Output Data: {json.dumps(task_data.get('output_data'), indent=2)}")
        print(f"   Updated at: {task_data.get('updated_at')}")
        print(f"   Completed at: {task_data.get('completed_at')}")
    else:
        print(f"❌ Failed to get task: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    check_task_status()