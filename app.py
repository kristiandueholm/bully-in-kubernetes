import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import sys

from kubernetes import client, config
from kubernetes.client.rest import ApiException

timeout_seconds = 30 # seconds
session_timeout =   aiohttp.ClientTimeout(total=None,sock_connect=timeout_seconds,sock_read=timeout_seconds)

POD_IP = str(os.environ['POD_IP'])
WEB_PORT = int(os.environ['WEB_PORT'])
POD_NAME = os.environ.get("POD_NAME")
POD_NAMESPACE = "default"
POD_ID = random.randint(0, 100)
LEADER = None

ELECTION_MODE = False

OTHER_PODS = dict()

def k8s_leader_label(leader_status: bool):
    '''
    Changes the label "leader" of the current pod to parameter leader_status.
    This determines what pod the nodeport is directed to.
    '''
    config.load_incluster_config()
    api_instance = client.CoreV1Api()

    new_label = {"leader": str(leader_status)}

    pod = api_instance.read_namespaced_pod(name=POD_NAME, namespace=POD_NAMESPACE)

    pod.metadata.labels.update(new_label)

    api_instance.patch_namespaced_pod(name=POD_NAME, namespace=POD_NAMESPACE, body=pod)

async def run_bully():
    global LEADER, OTHER_PODS
    while True:
        print("Running bully")
        print(f"Current leader for pod {POD_ID}: {LEADER}")

        # Reset list of pod ids
        await asyncio.sleep(5) # wait for everything to be up
        
        # Get all pods doing bully
        OTHER_PODS = dict()
        ip_list = []
        print("Making a DNS lookup to service")

        try:
            response = socket.getaddrinfo("bully-service-internal",0,0,0,0) # <-- DNS cache might take some time to update. 
        except:
            e_type, e_value, e_traceback = sys.exc_info()
            print("Got an exception:", e_type, e_value)

        print("Get response from DNS")
        print(f"DNS response: {response}")
        
        for result in response:
            ip_list.append(result[-1][0])
        ip_list = list(set(ip_list))
        
        print(f"IP_list: {ip_list}")

        # Remove own POD ip from the list of pods        
        try: 
            ip_list.remove(POD_IP)
        except ValueError: # <-- own ip not in the list, we don't care.
            print("Own ip not in list")
            pass

        print("Got %d other pod ip's" % (len(ip_list)))
     
   
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        for pod_ip in ip_list:
            endpoint = '/pod_id'
            url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
            try:
                async with aiohttp.ClientSession(timeout=session_timeout) as session:
                    async with session.get(url, timeout=1) as response:
                        response_data = await response.json()
                        OTHER_PODS[str(pod_ip)] = response_data
            except TimeoutError:
                print("Got timeout error") 
            except:
                    e_type, e_value, e_traceback = sys.exc_info()
                    print("Got an exception:", e_type, e_value)


        if ((LEADER is None or  # <-- initialized state
            LEADER not in OTHER_PODS.values() and LEADER is not POD_ID or  # <-- Leader fails/is deleted and not in list of pods && different from current pod
            POD_ID > max(OTHER_PODS.values()) or # <-- start new election if current pod has higher id than max in the list (other pods)
            LEADER < max(OTHER_PODS.values())) and  # < -- ensure that a pod doesn't take leader position if not highest id
            not ELECTION_MODE):
    
            await start_election()


        print("Sleeping now for 2 sec")
        # Sleep a bit, then repeat
        await asyncio.sleep(2)
    
#GET /pod_id
async def pod_id(request):
    print(f"Recieved GET: {request}")
    return web.json_response(POD_ID)
    
#POST /receive_ok
async def receive_ok(request):
    print("receive ok")
    global ELECTION_MODE
    ELECTION_MODE = False
    return web.Response(text="OK", status="200")

#POST /receive_election
async def receive_election(request):
    print("receive election")
    data = await request.json()
    sender_id = data['id']

    # Send OK to the node that initiated the election
    if sender_id < POD_ID:
        url = data['url']
        async with aiohttp.ClientSession(timeout=session_timeout) as session:
            await session.post(url, json={"msg": "OK", "status": 200}) # Url is /receive_ok
        await start_election() # Start the new election
    return web.Response(text="OK", status=200)


#POST /receive_coordinator
async def receive_coordinator(request):
    k8s_leader_label(False)
    print("receive coordinator")
    global LEADER, ELECTION_MODE
    try:
        data = await request.json()  # Parse the incoming JSON data
        LEADER = data["pod_id"]
        ELECTION_MODE = False
        return web.Response(text="OK", status=200)
    except Exception as e:
        print(f"Error processing coordinator request: {str(e)}")
        # Return an error response (HTTP status code 500 for internal server error)
        return web.Response(text="Internal Server Error", status=500)



async def start_election():
    print("start election")
    global LEADER, OTHER_PODS, ELECTION_MODE
    ELECTION_MODE = True
    other_higher_pods = {k: v for k, v in OTHER_PODS.items() if v > POD_ID}

    if not other_higher_pods:  # No higher pods, declare as leader
        LEADER = POD_ID
        await announce_leader()
    else:
        # Send ELECTION message to higher pods
        for pod_ip in other_higher_pods:
            url = 'http://' + pod_ip + ':' + str(WEB_PORT) + '/receive_election'
            try:
                async with aiohttp.ClientSession(timeout=session_timeout) as session:
                    await session.post(url, json={"id": POD_ID, "url": f"http://{POD_IP}:{WEB_PORT}/receive_ok"})
            except:
                pass  # Handle timeouts, errors, etc. if needed

# Announce to all other pods that current pod is the leader
async def announce_leader():
    print("Announce leader")
    k8s_leader_label(True)
    global OTHER_PODS
    for pod_ip in OTHER_PODS.keys():
        url = 'http://' + pod_ip + ':' + str(WEB_PORT) + '/receive_coordinator'
        try:
            async with aiohttp.ClientSession(timeout=session_timeout) as session:
                await session.post(url, json={"pod_id": POD_ID})
        except:
            pass  # handle errors, etc. if needed



async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task


from fortune_module import FortuneCookieJar
class FortuneService:
    def __init__(self):
        self.fortune_instance = FortuneCookieJar() 

    async def get_fortune(self, request):
        fortune = self.fortune_instance.get_random_fortune()
        return web.json_response({"fortune": fortune})


async def serve_website(request):
    """Serve the website or forward the request to the leader pod."""
    with open('index.html', 'r') as file:
        return web.Response(text=file.read(), content_type='text/html')
        

async def serve_fortune(request):
    """Serve a random fortune or forward the request to the leader pod."""
    print("serve_fortune")
    category = request.query.get("category", "all")
    fs = FortuneService()
    fs.fortune_instance.category  = category
    fortune = fs.fortune_instance.get_random_fortune()
    print(fortune)
    return web.json_response({"fortune": fortune})

if __name__ == "__main__":
    app = web.Application()
    app.router.add_static('/static/', path='static', name='static')
    app.router.add_get('/pod_id', pod_id)
    app.router.add_post('/receive_ok', receive_ok)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)

    app.router.add_get('/', serve_website)
    app.router.add_get('/fortune', serve_fortune)

    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host="0.0.0.0", port=WEB_PORT)

