
import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"

def post(endpoint, data):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

def get(endpoint):
    with urllib.request.urlopen(f"{BASE_URL}{endpoint}") as response:
        return response.status, json.loads(response.read().decode("utf-8"))

def run_tests():
    print("==================================================")
    print(">>> MOVIE TICKET BOOKING SYSTEM INTEGRATION SUITE <<<")
    print("==================================================")

    # 1. Fetch movies
    status, res = get("/api/movies")
    print(f"[TEST 1] Get Movies: Status {status}, Count = {len(res['data'])}")
    assert res["success"] == True

    # 2. Fetch seats for show 1
    status, res = get("/api/shows/1/seats")
    print(f"[TEST 2] Get Seats: Status {status}, Total = {len(res['data'])}")
    
    avail_seats = [s for s in res["data"] if s["status"] == "AVAILABLE"]
    print(f"Available Seats: {len(avail_seats)}")
    
    if len(avail_seats) < 5:
        print("Not enough available seats. Need at least 5 available seats for full run.")
        return

    s1, s2, s3, s4 = avail_seats[0], avail_seats[1], avail_seats[2], avail_seats[3]

    # 3. CASE 1: Single User Booking
    print(f"\n--- Testing Case 1: Single User Booking (Seat {s1['seat_number']}) ---")
    status, tx_res = post("/api/transactions/start", {"user_id": "User_1", "show_id": 1, "seat_id": s1["id"]})
    print(f"Start Transaction: {tx_res['message']}")
    assert tx_res["success"] == True
    tx_id = tx_res["transaction"]["transaction_id"]

    status, pay_res = post("/api/transactions/pay-counter", {"transaction_id": tx_id, "user_id": "User_1"})
    print(f"Pay at Counter: Code = {pay_res['booking']['random_code']}, Booking ID = {pay_res['booking']['booking_id']}")
    assert pay_res["success"] == True
    assert pay_res["booking"]["status"] == "BOOKED - PAY AT COUNTER"

    # 4. CASE 2: Two Users Select Same Seat (User 1 books, User 2 tries to proceed and is rejected)
    print(f"\n--- Testing Case 2: Two Users Select Same Seat (Seat {s2['seat_number']}) ---")
    status, tx2_res = post("/api/transactions/start", {"user_id": "User_1", "show_id": 1, "seat_id": s2["id"]})
    assert tx2_res["success"] == True
    tx2_id = tx2_res["transaction"]["transaction_id"]

    status, pay2_a_res = post("/api/transactions/pay-counter", {"transaction_id": tx2_id, "user_id": "User_1"})
    assert pay2_a_res["success"] == True
    print(f"User 1 successfully booked Seat {s2['seat_number']}. Code = {pay2_a_res['booking']['random_code']}")

    # User 2 tries to select / start transaction on Seat s2 after User 1 booked it
    try:
        status, tx2_b_res = post("/api/transactions/start", {"user_id": "User_2", "show_id": 1, "seat_id": s2["id"]})
    except urllib.error.HTTPError as e:
        err_body = json.loads(e.read().decode("utf-8"))
        print(f"User 2 Selection Rejection Message: '{err_body['detail']}'")
        assert err_body['detail'] == "This seat is already booked. Please select any other seat."

    # 5. CASE 3: Simultaneous Payment Click (Concurrency Race Condition)
    print(f"\n--- Testing Case 3: Simultaneous Payment Click (Seat {s3['seat_number']}) ---")
    status, race_res = post("/api/simulate/race-condition", {"show_id": 1, "seat_id": s3["id"]})
    print(f"Race Condition Result:")
    print(f"  User A: {race_res['user_a_result'].get('message', race_res['user_a_result'].get('detail'))}")
    print(f"  User B: {race_res['user_b_result'].get('detail', race_res['user_b_result'].get('message'))}")
    print(f"  Verdict: {race_res['explanation']}")
    assert race_res["success"] == True

    # 6. TEST 15-MINUTE TIMEOUT EXPIRY
    print(f"\n--- Testing 15-Minute Timeout Expiry (Seat {s4['seat_number']}) ---")
    status, tx4_res = post("/api/transactions/start", {"user_id": "User_1", "show_id": 1, "seat_id": s4["id"]})
    tx4_id = tx4_res["transaction"]["transaction_id"]
    
    # Trigger force expire
    status, exp_res = post("/api/transactions/expire-now", {"transaction_id": tx4_id, "user_id": "User_1"})
    print(f"Expiry Response Message: '{exp_res['message']}'")
    assert exp_res["message"] == "Transaction cancelled. Please try again. The seat is now available."

    print("\n==================================================")
    print("ALL TESTS PASSED PERFECTLY WITH 100% COMPLIANCE!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
