import sqlite3
import random
import string
import uuid
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "movie_booking.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Movies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        genre TEXT NOT NULL,
        duration TEXT NOT NULL,
        rating TEXT NOT NULL,
        poster_url TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT NOT NULL
    );
    """)

    # Shows table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        show_time TEXT NOT NULL,
        hall_name TEXT NOT NULL,
        FOREIGN KEY(movie_id) REFERENCES movies(id)
    );
    """)

    # Seats table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show_id INTEGER NOT NULL,
        seat_number TEXT NOT NULL,
        seat_row TEXT NOT NULL,
        seat_col INTEGER NOT NULL,
        seat_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'AVAILABLE',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(show_id) REFERENCES shows(id),
        UNIQUE(show_id, seat_number)
    );
    """)

    # Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        show_id INTEGER NOT NULL,
        seat_id INTEGER NOT NULL,
        seat_number TEXT NOT NULL,
        status TEXT NOT NULL,
        random_code TEXT,
        booking_id TEXT,
        start_time TIMESTAMP NOT NULL,
        expires_time TIMESTAMP NOT NULL,
        completed_time TIMESTAMP,
        FOREIGN KEY(show_id) REFERENCES shows(id),
        FOREIGN KEY(seat_id) REFERENCES seats(id)
    );
    """)

    conn.commit()

    # Seed data if empty
    cursor.execute("SELECT COUNT(*) as count FROM movies;")
    if cursor.fetchone()["count"] == 0:
        cursor.executemany("""
        INSERT INTO movies (title, genre, duration, rating, poster_url, price, description)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, [
            (
                "Interstellar: IMAX Special",
                "Sci-Fi / Adventure",
                "2h 49m",
                "PG-13",
                "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600&auto=format&fit=crop&q=80",
                14.50,
                "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival."
            ),
            (
                "Cyberpunk Odyssey 2099",
                "Action / Sci-Fi",
                "2h 15m",
                "R",
                "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&auto=format&fit=crop&q=80",
                13.00,
                "In a dystopian future, a rogue hacker unravels a conspiracy that spans across mega-corporations and neural nets."
            ),
            (
                "Avatar: Fire and Ash",
                "Action / Sci-Fi / Fantasy",
                "3h 10m",
                "PG-13",
                "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
                16.00,
                "Jake Sully and Neytiri explore new regions of Pandora and encounter a passionate, aggressive Na'vi volcanic tribe."
            )
        ])
        conn.commit()

        # Seed shows
        cursor.execute("SELECT id FROM movies;")
        movies = cursor.fetchall()
        for movie in movies:
            movie_id = movie["id"]
            shows_data = [
                (movie_id, "2026-08-18 14:30", "Screen 1 - Dolby Cinema"),
                (movie_id, "2026-08-18 18:00", "Screen 1 - Dolby Cinema"),
                (movie_id, "2026-08-18 21:15", "Screen 2 - IMAX 3D")
            ]
            cursor.executemany("INSERT INTO shows (movie_id, show_time, hall_name) VALUES (?, ?, ?);", shows_data)
        conn.commit()

        # Seed seats for all shows
        cursor.execute("SELECT id FROM shows;")
        shows = cursor.fetchall()
        rows = ["A", "B", "C", "D", "E"]
        for show in shows:
            show_id = show["id"]
            seats_data = []
            for r_idx, r in enumerate(rows):
                # Row A, B = Standard ($12), Row C, D = VIP ($15), Row E = Recliner ($18)
                if r in ["A", "B"]:
                    stype = "Standard"
                elif r in ["C", "D"]:
                    stype = "VIP"
                else:
                    stype = "Recliner"

                for col in range(1, 11):
                    seat_num = f"{r}{col}"
                    seats_data.append((show_id, seat_num, r, col, stype, "AVAILABLE"))
            
            cursor.executemany("""
            INSERT INTO seats (show_id, seat_number, seat_row, seat_col, seat_type, status)
            VALUES (?, ?, ?, ?, ?, ?);
            """, seats_data)
        conn.commit()

    conn.close()

def cleanup_expired_transactions(conn=None):
    """Auto-releases seats where 15-minute transaction window has expired."""
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True

    try:
        now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.cursor()
        
        # Find expired transactions
        cursor.execute("""
            SELECT id, seat_id FROM transactions 
            WHERE status = 'IN_TRANSACTION' AND expires_time <= ?
        """, (now_iso,))
        expired = cursor.fetchall()

        if expired:
            expired_tx_ids = [r["id"] for r in expired]
            expired_seat_ids = [r["seat_id"] for r in expired]
            
            # Reset seats to AVAILABLE
            cursor.execute(f"""
                UPDATE seats SET status = 'AVAILABLE', updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({','.join(['?']*len(expired_seat_ids))}) AND status = 'IN_TRANSACTION'
            """, expired_seat_ids)

            # Mark transactions as EXPIRED
            cursor.execute(f"""
                UPDATE transactions SET status = 'EXPIRED'
                WHERE id IN ({','.join(['?']*len(expired_tx_ids))})
            """, expired_tx_ids)

            conn.commit()
    finally:
        if close_conn:
            conn.close()

def get_movies():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies;")
    movies = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return movies

def get_shows(movie_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if movie_id:
        cursor.execute("""
            SELECT s.*, m.title, m.poster_url, m.price 
            FROM shows s JOIN movies m ON s.movie_id = m.id
            WHERE s.movie_id = ?;
        """, (movie_id,))
    else:
        cursor.execute("""
            SELECT s.*, m.title, m.poster_url, m.price 
            FROM shows s JOIN movies m ON s.movie_id = m.id;
        """)
    shows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return shows

def get_seats(show_id, current_user_id=None):
    """Fetches seat states for a show after cleaning up any expired transactions."""
    conn = get_db()
    cleanup_expired_transactions(conn)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, 
               t.id as active_transaction_id,
               t.user_id as transaction_user_id,
               t.expires_time
        FROM seats s
        LEFT JOIN transactions t ON s.id = t.seat_id AND t.status = 'IN_TRANSACTION'
        WHERE s.show_id = ?
        ORDER BY s.seat_row ASC, s.seat_col ASC;
    """, (show_id,))
    
    seats = []
    now_dt = datetime.utcnow()

    for row in cursor.fetchall():
        seat = dict(row)
        # Calculate remaining seconds for IN_TRANSACTION
        if seat["status"] == "IN_TRANSACTION" and seat["expires_time"]:
            exp_dt = datetime.strptime(seat["expires_time"], "%Y-%m-%d %H:%M:%S")
            rem_sec = max(0, int((exp_dt - now_dt).total_seconds()))
            seat["remaining_seconds"] = rem_sec
            seat["is_current_user_tx"] = (seat["transaction_user_id"] == current_user_id)
        else:
            seat["remaining_seconds"] = 0
            seat["is_current_user_tx"] = False
        
        seats.append(seat)

    conn.close()
    return seats

def start_transaction(user_id: str, show_id: int, seat_id: int):
    """Starts a 15-minute transaction for a seat atomically using IMMEDIATE transaction."""
    conn = get_db()
    cleanup_expired_transactions(conn)

    cursor = conn.cursor()
    try:
        # Atomic lock
        cursor.execute("BEGIN IMMEDIATE;")

        # Verify seat availability
        cursor.execute("""
            SELECT id, seat_number, status FROM seats WHERE id = ? AND show_id = ?;
        """, (seat_id, show_id))
        seat = cursor.fetchone()

        if not seat:
            conn.rollback()
            return {"success": False, "message": "Seat not found.", "status_code": 404}

        if seat["status"] != "AVAILABLE":
            conn.rollback()
            if seat["status"] == "BOOKED":
                msg = "This seat is already booked. Please select any other seat."
            else:
                msg = "This seat is currently in another transaction. Please select any other seat."
            return {"success": False, "message": msg, "status_code": 409}

        # Reserve seat temporarily
        cursor.execute("""
            UPDATE seats 
            SET status = 'IN_TRANSACTION', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'AVAILABLE';
        """, (seat_id,))

        if cursor.rowcount == 0:
            conn.rollback()
            return {
                "success": False, 
                "message": "This seat is already booked or in transaction. Please select any other seat.", 
                "status_code": 409
            }

        # Create 15-minute transaction
        tx_id = f"TX-{uuid.uuid4().hex[:10].upper()}"
        start_time = datetime.utcnow()
        expires_time = start_time + timedelta(minutes=15)
        
        start_iso = start_time.strftime("%Y-%m-%d %H:%M:%S")
        expires_iso = expires_time.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO transactions (id, user_id, show_id, seat_id, seat_number, status, start_time, expires_time)
            VALUES (?, ?, ?, ?, ?, 'IN_TRANSACTION', ?, ?);
        """, (tx_id, user_id, show_id, seat_id, seat["seat_number"], start_iso, expires_iso))

        conn.commit()
        return {
            "success": True,
            "message": "15-minute transaction initiated. Please complete payment before timeout.",
            "transaction": {
                "transaction_id": tx_id,
                "user_id": user_id,
                "show_id": show_id,
                "seat_id": seat_id,
                "seat_number": seat["seat_number"],
                "status": "IN_TRANSACTION",
                "start_time": start_iso,
                "expires_time": expires_iso,
                "remaining_seconds": 900
            }
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Server error: {str(e)}", "status_code": 500}
    finally:
        conn.close()

def cancel_transaction(transaction_id: str, user_id: str):
    """Cancels an active transaction and releases seat to AVAILABLE immediately."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        cursor.execute("""
            SELECT * FROM transactions WHERE id = ? AND user_id = ? AND status = 'IN_TRANSACTION';
        """, (transaction_id, user_id))
        tx = cursor.fetchone()

        if not tx:
            conn.rollback()
            return {
                "success": False,
                "message": "Transaction not found or already completed/expired.",
                "status_code": 404
            }

        # Update seat back to AVAILABLE
        cursor.execute("""
            UPDATE seats SET status = 'AVAILABLE', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'IN_TRANSACTION';
        """, (tx["seat_id"],))

        # Mark transaction CANCELLED
        cursor.execute("""
            UPDATE transactions SET status = 'CANCELLED' WHERE id = ?;
        """, (transaction_id,))

        conn.commit()
        return {
            "success": True,
            "message": "Transaction cancelled. Please try again. The seat is now available."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e), "status_code": 500}
    finally:
        conn.close()

def force_expire_transaction(transaction_id: str, user_id: str):
    """Forces immediate expiration of a transaction for testing purposes."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        cursor.execute("""
            SELECT * FROM transactions WHERE id = ? AND status = 'IN_TRANSACTION';
        """, (transaction_id,))
        tx = cursor.fetchone()

        if not tx:
            conn.rollback()
            return {
                "success": False,
                "message": "Transaction not found or already completed.",
                "status_code": 404
            }

        cursor.execute("""
            UPDATE seats SET status = 'AVAILABLE', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'IN_TRANSACTION';
        """, (tx["seat_id"],))

        cursor.execute("""
            UPDATE transactions SET status = 'EXPIRED' WHERE id = ?;
        """, (transaction_id,))

        conn.commit()
        return {
            "success": True,
            "message": "Transaction cancelled. Please try again. The seat is now available."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e), "status_code": 500}
    finally:
        conn.close()

def generate_random_code():
    chars = string.ascii_uppercase + string.digits
    return "PAY-" + "".join(random.choices(chars, k=6))

def generate_booking_id():
    return "BK-" + datetime.utcnow().strftime("%Y%m%d") + "-" + "".join(random.choices(string.digits, k=4))

def pay_at_counter(transaction_id: str, user_id: str):
    """
    Atomic transaction completion for 'Pay at Counter'.
    Transitions seat from IN_TRANSACTION -> BOOKED.
    Generates unique random payment code and booking ID.
    Handles Case 1, Case 2, and Case 3 concurrency race conditions cleanly.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Atomic lock
        cursor.execute("BEGIN IMMEDIATE;")
        
        # Check transaction
        cursor.execute("""
            SELECT t.*, s.seat_number, sh.show_time, sh.hall_name, m.title as movie_title, m.price, m.poster_url, m.genre
            FROM transactions t
            JOIN seats s ON t.seat_id = s.id
            JOIN shows sh ON t.show_id = sh.id
            JOIN movies m ON sh.movie_id = m.id
            WHERE t.id = ?;
        """, (transaction_id,))
        tx = cursor.fetchone()

        if not tx:
            conn.rollback()
            return {
                "success": False,
                "message": "Transaction record not found.",
                "status_code": 404
            }

        tx_dict = dict(tx)

        # Check if already processed
        if tx_dict["status"] == "BOOKED":
            conn.rollback()
            return {
                "success": True,
                "message": "Transaction completed successfully.",
                "already_booked": True,
                "booking": {
                    "booking_id": tx_dict["booking_id"],
                    "random_code": tx_dict["random_code"],
                    "seat_number": tx_dict["seat_number"],
                    "movie_title": tx_dict["movie_title"],
                    "show_time": tx_dict["show_time"],
                    "hall_name": tx_dict["hall_name"],
                    "price": tx_dict["price"]
                }
            }

        # Expiry check
        now_dt = datetime.utcnow()
        exp_dt = datetime.strptime(tx_dict["expires_time"], "%Y-%m-%d %H:%M:%S")
        if now_dt >= exp_dt:
            # Revert seat
            cursor.execute("UPDATE seats SET status = 'AVAILABLE' WHERE id = ? AND status = 'IN_TRANSACTION';", (tx_dict["seat_id"],))
            cursor.execute("UPDATE transactions SET status = 'EXPIRED' WHERE id = ?;", (transaction_id,))
            conn.commit()
            return {
                "success": False,
                "message": "Transaction cancelled. Please try again. The seat is now available.",
                "status_code": 410,
                "expired": True
            }

        # Check user match
        if tx_dict["user_id"] != user_id:
            conn.rollback()
            return {
                "success": False,
                "message": "This seat is already booked. Please select any other seat.",
                "status_code": 403
            }

        # Verify seat status in seats table
        cursor.execute("SELECT status FROM seats WHERE id = ?;", (tx_dict["seat_id"],))
        seat_row = cursor.fetchone()
        
        if not seat_row or seat_row["status"] == "BOOKED":
            cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE id = ?;", (transaction_id,))
            conn.commit()
            return {
                "success": False,
                "message": "This seat is already booked. Please select any other seat.",
                "status_code": 409
            }

        # Permanently book seat
        cursor.execute("""
            UPDATE seats SET status = 'BOOKED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'IN_TRANSACTION';
        """, (tx_dict["seat_id"],))

        if cursor.rowcount == 0:
            cursor.execute("UPDATE transactions SET status = 'REJECTED' WHERE id = ?;", (transaction_id,))
            conn.commit()
            return {
                "success": False,
                "message": "This seat is already booked. Please select any other seat.",
                "status_code": 409
            }

        random_code = generate_random_code()
        booking_id = generate_booking_id()
        completed_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE transactions 
            SET status = 'BOOKED', random_code = ?, booking_id = ?, completed_time = ?
            WHERE id = ?;
        """, (random_code, booking_id, completed_iso, transaction_id))

        conn.commit()

        return {
            "success": True,
            "message": "Transaction completed successfully.",
            "sub_messages": [
                "Your seat is booked.",
                "Please show/provide the below code at the counter to pay and get your ticket."
            ],
            "booking": {
                "booking_id": booking_id,
                "random_code": random_code,
                "movie_title": tx_dict["movie_title"],
                "movie_genre": tx_dict["genre"],
                "show_time": tx_dict["show_time"],
                "hall_name": tx_dict["hall_name"],
                "seat_number": tx_dict["seat_number"],
                "price": tx_dict["price"],
                "user_id": user_id,
                "status": "BOOKED - PAY AT COUNTER"
            }
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Server error: {str(e)}", "status_code": 500}
    finally:
        conn.close()
