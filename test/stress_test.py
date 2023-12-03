import requests
import concurrent.futures
import time

async def send_get_request(url):
    try:
        start_time = time.time()
        response = await requests.get(url)
        end_time = time.time()

        # Calculate and print the response time
        response_time = end_time - start_time
        print(f"Request to {url} - Status Code: {response.status_code}, Response Time: {response_time:.4f} seconds")
    except requests.RequestException as e:
        print(f"Request to {url} failed: {e}")

if __name__ == "__main__":
    # Replace 'http://your-target-url' with the actual URL you want to test
    target_url = 'http://127.0.0.1:52835/'
    
    # Replace 10 with the number of requests you want to send
    num_requests = 1000

    # You can adjust the number of threads based on your testing needs
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        # Use a list comprehension to create a list of URLs to send requests to
        urls = [target_url for _ in range(num_requests)]
        
        # Use map to apply the function to each URL concurrently
        executor.map(send_get_request, urls)
