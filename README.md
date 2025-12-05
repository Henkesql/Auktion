<<<<<<< HEAD
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, URL, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

url = URL.create(
    drivername="postgresql+psycopg2",
    host="localhost",
    port="5432",
    username="postgres",
    password="Sommar27",
    database="flask_demo"
)

engine = create_engine(url)

app = Flask(__name__)
Session = sessionmaker(bind=engine)


# 1. Sök tillgängliga boenden (User story #5)
@app.get('/available-hotels')
def get_available_hotels():
    city = request.args.get('city', '')
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')

    if not city or not check_in or not check_out:
        return jsonify({"message": "City, check_in, and check_out parameters are required."}), 400

    with Session() as session:
        # Använd den befintliga funktionen från databasen
        result = session.execute(
            text("SELECT * FROM find_available_rooms(:city, :check_in, :check_out)"),
            {"city": f"%{city}%", "check_in": check_in, "check_out": check_out}
        ).fetchall()

        hotels_list = [
            {
                "hotel_name": row.hotel_name,
                "address": row.adress,
                "room_number": row.room_number,
                "room_type": row.room_type,
                "max_occupancy": row.max_occupancy
            } for row in result
        ]

    return jsonify(hotels_list), 200


# 2. Kontrollera om boende är fullbokat (User story #7)
@app.get('/hotels/<int:hotel_id>/availability')
def check_hotel_availability(hotel_id):
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')

    if not check_in or not check_out:
        return jsonify({"message": "check_in and check_out parameters are required."}), 400

    with Session() as session:
        # Kolla tillgängliga rum för specifikt hotell
        result = session.execute(
            text("""
                 SELECT COUNT(r.id)                                        as available_rooms,
                        CASE WHEN COUNT(r.id) = 0 THEN true ELSE false END as is_fully_booked
                 FROM hotel h
                          JOIN room r ON r.hotel_id = h.id
                          LEFT JOIN v_room_booked_ranges br ON br.room_id = r.id
                     AND br.booked_range && daterange(:check_in, :check_out, '[)')
                 WHERE h.id = :hotel_id
                   AND br.bookingsegment_id IS NULL
                 """),
            {"hotel_id": hotel_id, "check_in": check_in, "check_out": check_out}
        ).fetchone()

        if not result:
            return jsonify({"message": f"No hotel found with id {hotel_id}."}), 404

        availability = {
            "hotel_id": hotel_id,
            "available_rooms": result.available_rooms,
            "is_fully_booked": result.is_fully_booked
        }

    return jsonify(availability), 200


# 3. Se detaljerad hotellinformation (User story #20)
@app.get('/hotels/<int:hotel_id>')
def get_hotel_details(hotel_id):
    with Session() as session:
        # Hämta grundläggande hotellinfo
        result = session.execute(
            text("SELECT * FROM hotel WHERE id = :id"),
            {"id": hotel_id}
        ).fetchone()

        if not result:
            return jsonify({"message": f"No hotel found with id {hotel_id}."}), 404

        # Hämta faciliteter
        amenities = session.execute(
            text("SELECT amenity FROM hotel_amenity WHERE hotel_id = :hotel_id"),
            {"hotel_id": hotel_id}
        ).fetchall()

        # Hämta rum
        rooms = session.execute(
            text("SELECT * FROM room WHERE hotel_id = :hotel_id"),
            {"hotel_id": hotel_id}
        ).fetchall()

        hotel_details = {
            "id": result.id,
            "hotel_name": result.hotel_name,
            "description": result.description,
            "address": result.adress,
            "city": result.city,
            "country": result.country,
            "property_type": result.property_type,
            "rating": float(result.rating) if result.rating else None,
            "amenities": [amenity.amenity for amenity in amenities],
            "rooms": [
                {
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "max_occupancy": room.max_occupancy,
                    "status": room.status
                } for room in rooms
            ]
        }

    return jsonify(hotel_details), 200


# 4. Filtrera hotell efter typ (User story #8)
@app.get('/hotels')
def get_hotels_by_type():
    property_type = request.args.get('property_type')

    query = "SELECT * FROM hotel"
    params = {}

    if property_type:
        query += " WHERE property_type = :property_type"
        params["property_type"] = property_type

    with Session() as session:
        result = session.execute(text(query), params).fetchall()

        hotels_list = [
            {
                "id": row.id,
                "hotel_name": row.hotel_name,
                "city": row.city,
                "country": row.country,
                "property_type": row.property_type,
                "rating": float(row.rating) if row.rating else None,
                "address": row.adress
            } for row in result
        ]

    return jsonify(hotels_list), 200


# 5. Se alla bokningar (Admin - User story #9)
@app.get('/admin/bookings')
def get_all_bookings():
    with Session() as session:
        result = session.execute(text("SELECT * FROM v_admin_bookings")).fetchall()

        bookings_list = [
            {
                "booking_id": row.booking_id,
                "customer_name": row.customer_name,
                "customer_email": row.customer_email,
                "booking_status": row.booking_status,
                "total_price": float(row.total_price_from_segments) if row.total_price_from_segments else 0,
                "adult_count": row.adult_count,
                "child_count": row.child_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "first_check_in": row.first_check_in.isoformat() if row.first_check_in else None,
                "last_check_out": row.last_check_out.isoformat() if row.last_check_out else None
            } for row in result
        ]

    return jsonify(bookings_list), 200


# 6. CRUD för hotell (Admin - User story #17)
@app.post('/admin/hotels')
def create_hotel():
    with Session() as session:
        data = request.get_json()

        required_fields = ["hotel_name", "city", "country", "address"]
        for field in required_fields:
            if field not in data:
                return jsonify({"message": f"Missing required field: {field}"}), 400

        session.execute(text("""
                             INSERT INTO hotel (hotel_name, description, adress, city, country, property_type, rating,
                                                latitude, longitude)
                             VALUES (:hotel_name, :description, :adress, :city, :country, :property_type, :rating,
                                     :latitude, :longitude)
                             """), {
                            "hotel_name": data.get("hotel_name"),
                            "description": data.get("description", ""),
                            "adress": data.get("address"),
                            "city": data.get("city"),
                            "country": data.get("country"),
                            "property_type": data.get("property_type"),
                            "rating": data.get("rating"),
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude")
                        })

        session.commit()

    return jsonify({"message": f"Hotel '{data.get('hotel_name')}' was created successfully."}), 201


@app.put('/admin/hotels/<int:hotel_id>')
def update_hotel(hotel_id):
    with Session() as session:
        data = request.get_json()

        # Kontrollera att hotellet finns
        existing = session.execute(
            text("SELECT id FROM hotel WHERE id = :id"),
            {"id": hotel_id}
        ).fetchone()

        if not existing:
            return jsonify({"message": f"No hotel found with id {hotel_id}."}), 404

        # Uppdatera hotellet
        session.execute(text("""
                             UPDATE hotel
                             SET hotel_name    = COALESCE(:hotel_name, hotel_name),
                                 description   = COALESCE(:description, description),
                                 adress        = COALESCE(:adress, adress),
                                 city          = COALESCE(:city, city),
                                 country       = COALESCE(:country, country),
                                 property_type = COALESCE(:property_type, property_type),
                                 rating        = COALESCE(:rating, rating),
                                 latitude      = COALESCE(:latitude, latitude),
                                 longitude     = COALESCE(:longitude, longitude)
                             WHERE id = :id
                             """), {
                            "id": hotel_id,
                            "hotel_name": data.get("hotel_name"),
                            "description": data.get("description"),
                            "adress": data.get("address"),
                            "city": data.get("city"),
                            "country": data.get("country"),
                            "property_type": data.get("property_type"),
                            "rating": data.get("rating"),
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude")
                        })

        session.commit()

    return jsonify({"message": f"Hotel with id {hotel_id} was updated successfully."}), 200


@app.delete('/admin/hotels/<int:hotel_id>')
def delete_hotel(hotel_id):
    with Session() as session:
        # Kontrollera att hotellet finns
        existing = session.execute(
            text("SELECT id FROM hotel WHERE id = :id"),
            {"id": hotel_id}
        ).fetchone()

        if not existing:
            return jsonify({"message": f"No hotel found with id {hotel_id}."}), 404

        session.execute(text("DELETE FROM hotel WHERE id = :id"), {"id": hotel_id})
        session.commit()

    return jsonify({"message": f"Hotel with id {hotel_id} was deleted."}), 200


if __name__ == '__main__':
    app.run(debug=True)
=======
# Prispressaren
>>>>>>> e3466b5d8a799138d9d3f6a8c4fd31314c8072b5
