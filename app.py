import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import requests

# POD_IP = str(os.environ['POD_IP'])
POD_IP = "127.0.0.1"
WEB_PORT = 8080
# WEB_PORT = int(os.environ['WEB_PORT'])
POD_ID = random.randint(0, 100)
COORDINATOR = None

async def setup_k8s():
    # If you need to do setup of Kubernetes, i.e. if using Kubernetes Python client
	print("K8S setup completed")
 
async def run_bully():
    while True:
        print("Running bully")
        await asyncio.sleep(5) # wait for everything to be up
        
        # Get all pods doing bully
        ip_list = []
        print("Making a DNS lookup to service")
        response = socket.getaddrinfo("bully-service",0,0,0,0)
        print("Get response from DNS")
        for result in response:
            ip_list.append(result[-1][0])
        ip_list = list(set(ip_list))
        
        # Remove own POD ip from the list of pods
        ip_list.remove(POD_IP)
        print("Got %d other pod ip's" % (len(ip_list)))
        
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        other_pods = dict()
        for pod_ip in ip_list:
            endpoint = '/pod_id'
            url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
            response = requests.get(url)
            other_pods[str(pod_ip)] = response.json()
            
        # Other pods in network
        print(other_pods)

        # If leader is not in pool of pods
            # Elect new leader
        
        
        
        # Sleep a bit, then repeat
        await asyncio.sleep(2)
    

#GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)
    
#POST /receive_ok
async def receive_ok(request):
    pass

#POST /receive_election
# Request should have id of sender and url where it expects answers. 
async def receive_election(request):
    data = await request.json()
    id = data['id']
    if id < POD_ID:


        url = data['url']
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"msg": "OK", "status": 200})

        # Send other election messages

        
        # start Election

        pass

#POST /receive_coordinator
async def receive_coordinator(request):
    try:
        global COORDINATOR
        data = await request.json()  # Parse the incoming JSON data

        COORDINATOR = data["pod_id"]

        return web.Response(text="OK", status=200)

    except Exception as e:
        print(f"Error processing coordinator request: {str(e)}")
        # Return an error response (HTTP status code 500 for internal server error)
        return web.Response(text="Internal Server Error", status=500)

async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/pod_id', pod_id)
    app.router.add_post('/receive_ok', receive_ok)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='127.0.0.1', port=8080)
