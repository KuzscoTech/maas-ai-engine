#!/usr/bin/env python3
"""
Complete MAAS Platform Demo with Authentication

This script demonstrates the full authenticated workflow:
1. User registration/login
2. Task creation with real AI processing
3. Progress monitoring
4. Server disconnection testing

Usage: python complete_demo.py
"""

import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class AuthenticatedMAASDemoClient:
    """Demo client with full authentication support"""
    
    def __init__(self):
        self.platform_url = "http://localhost:8000"
        self.ai_engine_url = "http://localhost:8001"
        self.access_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
        
    def make_authenticated_request(self, url: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an authenticated HTTP request"""
        headers = {}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        if data:
            headers["Content-Type"] = "application/json"
            request_data = json.dumps(data).encode('utf-8')
        else:
            request_data = None
        
        req = urllib.request.Request(url, data=request_data, headers=headers)
        req.get_method = lambda: method
        
        try:
            response = urllib.request.urlopen(req, timeout=10)
            response_data = json.loads(response.read().decode())
            return {"success": True, "data": response_data, "status": response.status}
        except urllib.error.HTTPError as e:
            error_data = {}
            try:
                error_data = json.loads(e.read().decode())
            except:
                error_data = {"detail": str(e)}
            return {"success": False, "error": error_data, "status": e.code}
        except Exception as e:
            return {"success": False, "error": {"detail": str(e)}, "status": 0}
    
    def register_demo_user(self) -> bool:
        """Register a demo user"""
        user_data = {
            "email": "demo@maas-platform.dev",
            "password": "DemoPassword123!",
            "confirm_password": "DemoPassword123!",
            "full_name": "MAAS Demo User",
            "organization_name": "MAAS Demo Organization"
        }
        
        print(f"{Colors.OKCYAN}👤 Registering demo user...{Colors.ENDC}")
        
        result = self.make_authenticated_request(
            f"{self.platform_url}/api/v1/auth/register",
            method="POST",
            data=user_data
        )
        
        if result["success"]:
            print(f"{Colors.OKGREEN}✅ Demo user registered successfully{Colors.ENDC}")
            return True
        elif result["status"] == 400 and "already registered" in str(result["error"]).lower():
            print(f"{Colors.WARNING}ℹ️ Demo user already exists{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.FAIL}❌ Registration failed: {result['error']}{Colors.ENDC}")
            return False
    
    def login_demo_user(self) -> bool:
        """Login as demo user"""
        login_data = {
            "email": "demo@maas-platform.dev",
            "password": "DemoPassword123!"
        }
        
        print(f"{Colors.OKCYAN}🔐 Logging in...{Colors.ENDC}")
        
        result = self.make_authenticated_request(
            f"{self.platform_url}/api/v1/auth/login",
            method="POST",
            data=login_data
        )
        
        if result["success"]:
            response_data = result["data"]
            self.access_token = response_data.get("access_token")
            self.user_info = response_data.get("user", {})
            print(f"{Colors.OKGREEN}✅ Login successful! Welcome {self.user_info.get('full_name', 'User')}{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.FAIL}❌ Login failed: {result['error']}{Colors.ENDC}")
            return False
    
    def check_system_health(self):
        """Check health of all system components"""
        print(f"\n{Colors.HEADER}🔍 MAAS Platform System Status{Colors.ENDC}")
        print("=" * 60)
        
        # Check Platform
        result = self.make_authenticated_request(f"{self.platform_url}/api/v1/health")
        if result["success"]:
            print(f"📊 Platform Server (8000): {Colors.OKGREEN}healthy{Colors.ENDC}")
        else:
            print(f"📊 Platform Server (8000): {Colors.FAIL}disconnected{Colors.ENDC}")
        
        # Check AI Engine
        try:
            response = urllib.request.urlopen(f"{self.ai_engine_url}/health", timeout=5)
            if response.status == 200:
                print(f"🤖 AI Engine (8001): {Colors.OKGREEN}healthy{Colors.ENDC}")
            else:
                print(f"🤖 AI Engine (8001): {Colors.FAIL}error{Colors.ENDC}")
        except:
            print(f"🤖 AI Engine (8001): {Colors.FAIL}disconnected{Colors.ENDC}")
        
        print()
    
    def create_task(self, title: str, description: str, parameters: Dict[str, Any] = None) -> Optional[str]:
        """Create a task via the authenticated API"""
        task_data = {
            "title": title,
            "description": description,
            "parameters": parameters or {},
            "priority": "medium"
        }
        
        print(f"{Colors.OKCYAN}📝 Creating task: {title}...{Colors.ENDC}")
        
        result = self.make_authenticated_request(
            f"{self.platform_url}/api/v1/tasks/simple",
            method="POST",
            data=task_data
        )
        
        if result["success"]:
            task_data = result["data"]
            task_id = task_data.get("id")
            print(f"{Colors.OKGREEN}✅ Task created successfully: {task_id}{Colors.ENDC}")
            return task_id
        else:
            print(f"{Colors.FAIL}❌ Failed to create task: {result['error']}{Colors.ENDC}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current task status"""
        result = self.make_authenticated_request(f"{self.platform_url}/api/v1/tasks/{task_id}")
        
        if result["success"]:
            return result["data"]
        else:
            print(f"{Colors.WARNING}⚠️ Could not fetch task status: {result['error']}{Colors.ENDC}")
            return None
    
    def monitor_task(self, task_id: str, timeout: int = 90):
        """Monitor task progress by polling"""
        print(f"{Colors.OKBLUE}👀 Monitoring task progress for {task_id}...{Colors.ENDC}")
        
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout:
            task_data = self.get_task_status(task_id)
            
            if task_data:
                status = task_data.get("status", "unknown")
                
                if status != last_status:
                    if status == "CREATED" or status == "QUEUED":
                        print(f"{Colors.WARNING}⏳ Status: {status} - Waiting for AI Engine{Colors.ENDC}")
                    elif status == "IN_PROGRESS":
                        print(f"{Colors.WARNING}⚡ Status: {status} - AI agent processing with Google ADK...{Colors.ENDC}")
                    elif status == "COMPLETED":
                        print(f"{Colors.OKGREEN}🎉 Task completed successfully!{Colors.ENDC}")
                        
                        # Show output if available
                        if "output_data" in task_data:
                            print(f"{Colors.OKCYAN}📄 AI Generated Output:{Colors.ENDC}")
                            output = task_data["output_data"]
                            if isinstance(output, dict):
                                for key, value in output.items():
                                    print(f"   {key}: {str(value)[:300]}...")
                            else:
                                print(f"   {str(output)[:500]}...")
                        
                        return True
                    elif status == "FAILED":
                        error_msg = task_data.get("error_message", "Unknown error")
                        print(f"{Colors.FAIL}💥 Task failed: {error_msg}{Colors.ENDC}")
                        return False
                    
                    last_status = status
                else:
                    print(".", end="", flush=True)
            
            time.sleep(3)
        
        print(f"\n{Colors.WARNING}⏰ Monitoring timeout reached{Colors.ENDC}")
        return False
    
    def run_workflow_test(self, task_title: str, task_description: str, task_parameters: Dict[str, Any] = None):
        """Run complete workflow test"""
        print(f"\n{Colors.HEADER}🚀 Starting Complete Workflow Test{Colors.ENDC}")
        print("=" * 60)
        
        # 1. Check system health
        self.check_system_health()
        
        # 2. Ensure authentication
        if not self.access_token:
            print(f"{Colors.WARNING}⚠️ Not authenticated. Setting up demo user...{Colors.ENDC}")
            if not self.register_demo_user() or not self.login_demo_user():
                print(f"{Colors.FAIL}❌ Authentication setup failed{Colors.ENDC}")
                return False
        
        # 3. Create task
        task_id = self.create_task(task_title, task_description, task_parameters)
        if not task_id:
            print(f"{Colors.FAIL}❌ Workflow failed: Could not create task{Colors.ENDC}")
            return False
        
        # 4. Monitor progress
        success = self.monitor_task(task_id, timeout=120)
        
        # 5. Final status
        final_status = self.get_task_status(task_id)
        if final_status:
            print(f"\n{Colors.OKBLUE}📋 Final Task Status:{Colors.ENDC}")
            print(f"   ID: {final_status.get('id')}")
            print(f"   Title: {final_status.get('title')}")
            print(f"   Status: {final_status.get('status')}")
            print(f"   Created: {final_status.get('created_at')}")
            if final_status.get('completed_at'):
                print(f"   Completed: {final_status.get('completed_at')}")
        
        return success


def main():
    """Main demo interface"""
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("🤖 MAAS Platform Complete Demo")
    print("==============================")
    print(f"{Colors.ENDC}")
    print("This demo shows the complete authenticated workflow:")
    print("• 🔐 User registration and authentication")
    print("• 📝 Task creation via API")
    print("• 🤖 Real Google ADK AI processing")
    print("• 📊 Live progress monitoring")
    print("• 🔌 Server disconnection resilience")
    print()
    
    demo = AuthenticatedMAASDemoClient()
    
    # Setup authentication
    print(f"{Colors.HEADER}🔐 Authentication Setup{Colors.ENDC}")
    print("=" * 40)
    
    if not demo.register_demo_user() or not demo.login_demo_user():
        print(f"{Colors.FAIL}❌ Could not set up authentication. Check server logs.{Colors.ENDC}")
        return
    
    while True:
        print(f"\n{Colors.BOLD}Available Demo Tests:{Colors.ENDC}")
        print("1. 📝 AI Code Generation (Real Google Gemini)")
        print("2. 🔍 AI Research Task (Real Google Gemini)")
        print("3. 🧪 AI Test Generation (Real Google Gemini)")
        print("4. 📊 Check System Status")
        print("5. 🔌 Test Server Disconnection Scenario")
        print("6. 🚪 Exit Demo")
        print()
        
        try:
            choice = input(f"{Colors.OKCYAN}Enter your choice (1-6): {Colors.ENDC}").strip()
        except EOFError:
            print(f"\n{Colors.WARNING}Demo terminated{Colors.ENDC}")
            break
        
        if choice == "1":
            language = input("Programming language (python/javascript/java): ").strip() or "python"
            description = input("What should the AI create? ").strip() or "a simple calculator with basic math operations"
            
            demo.run_workflow_test(
                f"AI Code Generation - {language.title()}",
                f"Create {language} code: {description}",
                {
                    "task_type": "code_generation",
                    "language": language,
                    "description": description,
                    "ai_model": "gemini-2.0-flash"
                }
            )
            
        elif choice == "2":
            topic = input("Research topic: ").strip() or "latest trends in artificial intelligence"
            
            demo.run_workflow_test(
                "AI Research Task",
                f"Research: {topic}",
                {
                    "task_type": "research",
                    "query": topic,
                    "depth": "comprehensive",
                    "ai_model": "gemini-2.0-flash"
                }
            )
            
        elif choice == "3":
            code_description = input("Code to generate tests for: ").strip() or "a basic calculator function"
            
            demo.run_workflow_test(
                "AI Test Generation",
                f"Generate tests for: {code_description}",
                {
                    "task_type": "testing",
                    "target": code_description,
                    "test_type": "unit",
                    "ai_model": "gemini-2.0-flash"
                }
            )
            
        elif choice == "4":
            demo.check_system_health()
            input(f"\n{Colors.OKCYAN}Press Enter to continue...{Colors.ENDC}")
            
        elif choice == "5":
            print(f"\n{Colors.WARNING}🔌 Server Disconnection Test{Colors.ENDC}")
            print("=" * 50)
            print("This demonstrates how the system handles disconnections:")
            print()
            print("🔄 Architecture:")
            print("  Platform (8000) ↔ Redis ↔ AI Engine (8001)")
            print()
            print("📋 Test Process:")
            print("1. Create a task")
            print("2. Kill a server: pkill -f 'python3 main.py' (AI Engine)")
            print("3. Watch task queue up")
            print("4. Restart server and see task resume")
            print()
            
            if input("Create test task? (y/n): ").lower() == 'y':
                demo.run_workflow_test(
                    "Disconnection Test Task",
                    "Test server disconnection resilience",
                    {"task_type": "test", "disconnection_test": True}
                )
            
        elif choice == "6":
            print(f"{Colors.OKGREEN}👋 Thanks for using the MAAS Platform Demo!{Colors.ENDC}")
            print()
            print("The platform is still running:")
            print("• Web UI: http://localhost:5173")
            print("• API Docs: http://localhost:8000/api/docs")
            print("• AI Engine: http://localhost:8001")
            break
            
        else:
            print(f"{Colors.FAIL}❌ Invalid choice{Colors.ENDC}")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}🛑 Demo interrupted{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}💥 Demo error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()