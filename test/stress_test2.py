import threading
import requests
from time import time

def send_req(avgs, lock):
    target_url = 'http://127.0.0.1:52835/'
    req_num = 100
    avg = 0
    for _ in range(req_num):
        try:
            start_time = time()
            response = requests.get(target_url)
            end_time = time()

            response_time = end_time - start_time
            avg += response_time
            # print(f"Response: {response}, time: {response_time}")

        except requests.RequestException as e:
            print(f"Request failed with exepction {e}")

    avg = avg/req_num
    with lock:
        avgs.append(avg)

def run_test(num_of_threads):
    lock = threading.Lock()
    avgs = []
    threads = []

    for _ in range(num_of_threads):
        th = threading.Thread(target=send_req, args=(avgs, lock))
        threads.append(th)
        
    # start threads
    for th in threads:
        th.start()

    for th in threads:
        th.join()

    print(f"Avg with {num_of_threads} threads is: {sum(avgs) / num_of_threads}")

if __name__ == "__main__":
    print("Running test 1 with 10 threads ✅:")
    run_test(10)
    print("Running test 2 with 1 thread ✅:")
    run_test(1)

    print("Running test 3 with 5 threads ✅:")
    run_test(5)

    print("Running test 4 with 25 threads ✅:")
    run_test(25)
    
    print("Running test 5 with 50 threads ✅:")
    run_test(50)