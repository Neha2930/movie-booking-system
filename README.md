# Movie Ticket Seat-Booking System (Worksheet 3 Compliant)

A production-grade, concurrency-safe movie ticket seat-booking application built with Python FastAPI, SQLite (WAL mode with atomic transaction locking), HTML5, Vanilla CSS design system, JavaScript, and jsPDF.

---

## Key Features & Worksheet 3 Requirements

1. **15-Minute Transaction Window**:
   - Starting payment initiates a visible 15-minute countdown (`MM:SS`) timer.
   - Selected seat transitions to `IN TRANSACTION` status (temporarily reserved, NOT permanently booked).
   - On 00:00 timeout or cancellation, seat is immediately released back to `AVAILABLE` for all users with the message:
     > *"Transaction cancelled. Please try again. The seat is available for another person."*

2. **Worksheet 3 Cases Implemented**:
   - **Case 1 (Single User)**: User selects seat -> clicks "Pay at Counter" -> seat is permanently marked `BOOKED` -> generates unique 8-character random payment code (e.g. `PAY-9X82K1`) and PDF receipt.
   - **Case 2 (Sequential Conflict)**: Two users select same seat. User 1 completes transaction first -> gets seat. User 2 attempting payment receives:
     > *"This seat is already booked. Please select any other seat."*
     User 2 is redirected to seat selection with updated seat states.
   - **Case 3 (Simultaneous Payment Click)**: Two users click payment at the exact same microsecond. Backend uses atomic SQLite database isolation (`BEGIN IMMEDIATE`). Exactly ONE transaction succeeds; the other is rejected safely with:
     > *"This seat is already booked. Please select any other seat."*

3. **Pay at Counter & ACT 2 PDF Receipt**:
   - ONE prominent **"Pay at Counter"** button.
   - Generates random code on screen + offers instant **"Download PDF Receipt"** containing Movie Title, Date, Showtime, Seat Number, Booking ID, Payment Code, and counter instructions.

4. **Seat States**:
   - `AVAILABLE`: Can be selected.
   - `SELECTED`: Selected in UI.
   - `IN TRANSACTION`: 15-minute temporary reservation.
   - `BOOKED`: Permanently unavailable.

---

## Folder Structure

```
movie-booking-system/
├── app/
│   ├── database.py       # SQLite WAL mode & atomic database transaction engine
│   └── main.py           # FastAPI application server & REST endpoints
├── static/
│   ├── index.html        # Glassmorphic cinema UI template
│   ├── styles.css        # Vanilla CSS theme & animation design system
│   ├── app.js            # Frontend state machine & 15-min countdown timer
│   └── simulator.js      # Interactive Concurrency & Race-Condition Test Suite
├── tests/
│   └── test_concurrency.py # Automated pytest/requests runner for Cases 1, 2, 3
├── movie_booking.db      # SQLite database (auto-generated)
└── README.md             # Project documentation
```

---

## Setup and Run Instructions

### Prerequisites
- Python 3.10+ (Python 3.13 tested)
- `fastapi`, `uvicorn`, `requests`, `pydantic` installed

### Quick Start Commands

1. **Navigate to project directory**:
   ```bash
   cd C:\Users\91821\.gemini\antigravity-ide\scratch\movie-booking-system
   ```

2. **Start the FastAPI Backend Server**:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **Open Application in Browser**:
   Open browser at: `http://127.0.0.1:8000`

---

## Testing Cases 1, 2, and 3

### Option A: Using the Built-In UI Test Suite
1. Open `http://127.0.0.1:8000`.
2. Locate the **"Concurrency Test Suite"** panel on the bottom-right sidebar.
3. Click **"Run Case 1"** -> Tests single user booking on seat C1.
4. Click **"Run Case 2"** -> Tests sequential conflict on seat C2.
5. Click **"Run Case 3"** -> Spawns 2 simultaneous server threads hitting payment at the exact same microsecond for seat C3.

### Option B: Using Automated Python Test Script
With server running, run:
```bash
python tests/test_concurrency.py
```
