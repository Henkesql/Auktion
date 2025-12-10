from flask import Flask, jsonify, request
from sqlalchemy import create_engine, URL, text
from sqlalchemy.orm import sessionmaker
import json
import traceback

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


# ========== USER ENDPOINTS ==========

# GET: Hämta alla användare
@app.get('/users')
def get_users():
    """Hämta alla användare för administratör"""
    with Session() as session:
        try:
            result = session.execute(text("""
                                          SELECT id, first_name, last_name, email, phone, role, created_at
                                          FROM "user"
                                          """)).fetchall()

            users_list = [
                {
                    "id": row.id,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "email": row.email,
                    "phone": row.phone,
                    "role": row.role,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                } for row in result
            ]

            return jsonify(users_list), 200

        except Exception as e:
            return jsonify({"message": f"Fel vid hämtning av användare: {str(e)}"}), 500


# POST: Skapa ny användare
@app.post('/users')
def create_user():
    """Registrera ny användare"""
    with Session() as session:
        try:
            data = request.get_json()

            if not data:
                return jsonify({"message": "Ingen data skickad"}), 400

            email = data.get("email")
            password = data.get("password")
            first_name = data.get("first_name", "")
            last_name = data.get("last_name", "")
            phone = data.get("phone", "")

            if not email or not password:
                return jsonify({"message": "E-post och lösenord krävs."}), 400

            # Kontrollera om användaren redan finns
            existing = session.execute(
                text('SELECT id FROM "user" WHERE email = :email'),
                {"email": email}
            ).fetchone()

            if existing:
                return jsonify({"message": "E-postadressen används redan."}), 409

            # Spara användare
            result = session.execute(
                text('''
                     INSERT INTO "user" (first_name, last_name, email, password, phone, role, created_at)
                     VALUES (:first_name, :last_name, :email, :password, :phone, :role, NOW()) RETURNING id
                     '''),
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "password": password,
                    "phone": phone,
                    "role": "customer"
                }
            )

            new_user_id = result.scalar()
            session.commit()

            return jsonify({
                "message": f"Användare skapad för {email}.",
                "user": {
                    "id": new_user_id,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "customer"
                }
            }), 201

        except Exception as e:
            session.rollback()
            return jsonify({"message": f"Fel vid skapande av användare: {str(e)}"}), 500


# POST: Logga in
@app.post('/login')
def login():
    """Logga in användare"""
    with Session() as session:
        try:
            data = request.get_json()
            if not data:
                return jsonify({"message": "Ingen data skickad"}), 400

            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return jsonify({"message": "E-post och lösenord krävs."}), 400

            # Hämta användare
            user = session.execute(
                text('SELECT * FROM "user" WHERE email = :email'),
                {"email": email}
            ).fetchone()

            if not user:
                return jsonify({"message": "Fel e-post eller lösenord."}), 401

            # Enkel lösenordsjämförelse
            if user.password != password:
                return jsonify({"message": "Fel e-post eller lösenord."}), 401

            # Returnera användarinformation
            user_data = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "message": "Inloggning lyckades"
            }

            return jsonify(user_data), 200

        except Exception as e:
            return jsonify({"message": f"Fel vid inloggning: {str(e)}"}), 500


# ========== HOTEL ENDPOINTS ==========

# GET: Kortfattad hotelllista
@app.get('/hotels')
def get_hotels_summary():
    """Hämta kortfattad lista över hotell"""
    with Session() as session:
        try:
            result = session.execute(text("""
                                          SELECT h.id,
                                                 h.hotel_name,
                                                 h.description,
                                                 h.images,
                                                 h.rating,
                                                 h.city,
                                                 h.country,
                                                 h.adress
                                          FROM hotel h
                                          ORDER BY h.rating DESC NULLS LAST
                                          """)).fetchall()

            hotels_list = []
            for row in result:
                hotel = {
                    "id": row.id,
                    "hotel_name": row.hotel_name,
                    "description": row.description,
                    "rating": float(row.rating) if row.rating else None,
                    "city": row.city,
                    "country": row.country,
                    "adress": row.adress
                }

                if row.images:
                    try:
                        images = json.loads(row.images)
                        hotel["main_image"] = images.get("main")
                    except:
                        hotel["main_image"] = None

                hotels_list.append(hotel)

            return jsonify(hotels_list), 200

        except Exception as e:
            return jsonify({"message": f"Fel vid hämtning av hotell: {str(e)}"}), 500


# GET: Detaljerad hotellinfo
@app.get('/hotels/<int:hotel_id>')
def get_hotel_details(hotel_id):
    """Hämta detaljerad hotellinformation"""
    with Session() as session:
        try:
            # Hämta hotellinformation
            hotel = session.execute(
                text("""
                     SELECT h.*
                     FROM hotel h
                     WHERE h.id = :id
                     """),
                {"id": hotel_id}
            ).fetchone()

            if not hotel:
                return jsonify({"message": f"Hotell med ID {hotel_id} finns inte."}), 404

            # Hämta faciliteter (amenities)
            amenities = session.execute(
                text("""
                     SELECT amenity
                     FROM hotel_amenity
                     WHERE hotel_id = :hotel_id
                     ORDER BY amenity
                     """),
                {"hotel_id": hotel_id}
            ).fetchall()

            # Hämta tillgängliga rum
            rooms = session.execute(
                text("""
                     SELECT r.id,
                            r.room_number,
                            r.room_type,
                            r.max_occupancy,
                            r.status
                     FROM room r
                     WHERE r.hotel_id = :hotel_id
                       AND r.status = 'available'
                     ORDER BY r.room_type, r.room_number
                     """),
                {"hotel_id": hotel_id}
            ).fetchall()

            # Hämta senaste pris från bookingsegment
            latest_prices = session.execute(
                text("""
                     SELECT r.id                                                              as room_id,
                            COALESCE(bs.price_per_night_reduced, bs.price_per_night_original) as latest_price
                     FROM room r
                              LEFT JOIN (SELECT DISTINCT
                                         ON (room_id) room_id, price_per_night_original, price_per_night_reduced
                                         FROM bookingsegment
                                         WHERE price_per_night_original IS NOT NULL
                                         ORDER BY room_id, check_in_date DESC) bs ON bs.room_id = r.id
                     WHERE r.hotel_id = :hotel_id
                     """),
                {"hotel_id": hotel_id}
            ).fetchall()

            # Skapa dictionary för priser
            price_dict = {row.room_id: float(row.latest_price) if row.latest_price else None for row in latest_prices}

            # Bygg detaljerad respons
            hotel_details = {
                "id": hotel.id,
                "hotel_name": hotel.hotel_name,
                "description": hotel.description,
                "address": hotel.adress,
                "city": hotel.city,
                "country": hotel.country,
                "property_type": hotel.property_type,
                "rating": float(hotel.rating) if hotel.rating else None,
                "coordinates": {
                    "latitude": float(hotel.latitude) if hotel.latitude else None,
                    "longitude": float(hotel.longitude) if hotel.longitude else None
                },
                "amenities": [amenity.amenity for amenity in amenities],
            }

            # Lägg till bilder om de finns
            if hotel.images:
                try:
                    hotel_details["images"] = json.loads(hotel.images)
                except:
                    hotel_details["images"] = hotel.images

            # Lägg till rum med priser
            hotel_details["rooms"] = [
                {
                    "id": room.id,
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "max_occupancy": room.max_occupancy,
                    "status": room.status,
                    "price_per_night": price_dict.get(room.id)
                } for room in rooms
            ]

            return jsonify(hotel_details), 200

        except Exception as e:
            return jsonify({"message": f"Fel vid hämtning av hotellinformation: {str(e)}"}), 500


# PUT: Uppdatera hotellinformation
@app.put('/hotels/<int:hotel_id>')
def update_hotel(hotel_id):
    """Uppdatera hotellinformation"""
    with Session() as session:
        try:
            data = request.get_json()

            if not data:
                return jsonify({"message": "Ingen data skickad"}), 400

            # Bygg dynamisk UPDATE query
            update_fields = []
            params = {"id": hotel_id}

            # Lägg till alla möjliga fält
            field_mappings = {
                "hotel_name": "hotel_name",
                "description": "description",
                "rating": "rating",
                "images": "images",
                "adress": "adress",
                "city": "city",
                "country": "country",
                "property_type": "property_type",
                "latitude": "latitude",
                "longitude": "longitude"
            }

            for json_field, db_field in field_mappings.items():
                if json_field in data:
                    if json_field == "images" and data[json_field] is not None:
                        # Konvertera till JSON-sträng om det inte redan är det
                        if isinstance(data[json_field], dict):
                            params[db_field] = json.dumps(data[json_field])
                        else:
                            params[db_field] = data[json_field]
                        update_fields.append(f"{db_field} = :{db_field}")
                    elif data[json_field] is not None:
                        params[db_field] = data[json_field]
                        update_fields.append(f"{db_field} = :{db_field}")

            if not update_fields:
                return jsonify({"message": "Inga fält att uppdatera."}), 400

            # Kontrollera att hotellet finns
            existing = session.execute(
                text("SELECT id, hotel_name FROM hotel WHERE id = :id"),
                {"id": hotel_id}
            ).fetchone()

            if not existing:
                return jsonify({"message": f"Hotell med ID {hotel_id} finns inte."}), 404

            # Utför uppdatering
            query = f"UPDATE hotel SET {', '.join(update_fields)} WHERE id = :id"
            session.execute(text(query), params)
            session.commit()

            # Hämta det uppdaterade hotellet
            updated_hotel = session.execute(
                text("""
                     SELECT id,
                            hotel_name,
                            description,
                            rating,
                            images,
                            adress,
                            city,
                            country,
                            property_type
                     FROM hotel
                     WHERE id = :id
                     """),
                {"id": hotel_id}
            ).fetchone()

            # Bygg response
            response_data = {
                "message": f"Hotell {hotel_id} uppdaterat.",
                "hotel": {
                    "id": updated_hotel.id,
                    "hotel_name": updated_hotel.hotel_name,
                    "description": updated_hotel.description,
                    "rating": float(updated_hotel.rating) if updated_hotel.rating else None,
                    "address": updated_hotel.adress,
                    "city": updated_hotel.city,
                    "country": updated_hotel.country,
                    "property_type": updated_hotel.property_type
                }
            }

            # Lägg till bilder om de finns
            if updated_hotel.images:
                try:
                    response_data["hotel"]["images"] = json.loads(updated_hotel.images)
                except:
                    response_data["hotel"]["images"] = updated_hotel.images

            return jsonify(response_data), 200

        except Exception as e:
            session.rollback()
            return jsonify({"message": f"Fel vid uppdatering av hotell: {str(e)}"}), 500


# ========== ROOM ENDPOINTS ==========

# POST: Lägg till nytt rum - FIXAD MED SEKVENSHANTERING
@app.post('/rooms')
def create_room():
    """Lägg till nytt rum i ett hotell"""
    with Session() as session:
        try:
            data = request.get_json()
            print(f"Received room data: {data}")

            if not data:
                return jsonify({"message": "Ingen data skickad"}), 400

            hotel_id = data.get("hotel_id")
            room_number = data.get("room_number")
            room_type = data.get("room_type")
            max_occupancy = data.get("max_occupancy")

            # Validera input
            missing_fields = []
            if not hotel_id:
                missing_fields.append("hotel_id")
            if not room_number:
                missing_fields.append("room_number")
            if not room_type:
                missing_fields.append("room_type")
            if not max_occupancy:
                missing_fields.append("max_occupancy")

            if missing_fields:
                return jsonify({"message": f"Saknade fält: {', '.join(missing_fields)}"}), 400

            # Kontrollera att hotellet finns
            hotel = session.execute(
                text("SELECT id, hotel_name FROM hotel WHERE id = :hotel_id"),
                {"hotel_id": hotel_id}
            ).fetchone()

            if not hotel:
                return jsonify({"message": f"Hotell med ID {hotel_id} finns inte."}), 404

            print(f"Hotel found: {hotel.hotel_name}")

            # Kontrollera om rummet redan finns
            existing = session.execute(
                text("""
                     SELECT id
                     FROM room
                     WHERE hotel_id = :hotel_id
                       AND room_number = :room_number
                     """),
                {"hotel_id": hotel_id, "room_number": room_number}
            ).fetchone()

            if existing:
                return jsonify({"message": f"Rum {room_number} finns redan på hotell {hotel_id}."}), 409

            # HÄMTA NÄSTA ID FRÅN SEKVENSEN MANUELLT
            print("Getting next ID from room_id_seq...")
            next_id_result = session.execute(
                text("SELECT nextval('room_id_seq')")
            ).fetchone()
            next_id = next_id_result[0]
            print(f"Next ID: {next_id}")

            # Lägg till rummet med explicit ID
            result = session.execute(
                text("""
                     INSERT INTO room (id, hotel_id, room_number, room_type, max_occupancy, status)
                     VALUES (:id, :hotel_id, :room_number, :room_type, :max_occupancy, 'available') RETURNING id
                     """),
                {
                    "id": next_id,
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "room_type": room_type,
                    "max_occupancy": int(max_occupancy)
                }
            )

            new_room_id = result.scalar()
            session.commit()
            print(f"Room created with ID: {new_room_id}")

            # Hämta det nya rummet
            new_room = session.execute(
                text("""
                     SELECT id, hotel_id, room_number, room_type, max_occupancy, status
                     FROM room
                     WHERE id = :id
                     """),
                {"id": new_room_id}
            ).fetchone()

            return jsonify({
                "message": f"Rum {room_number} tillagt på hotell {hotel.hotel_name}.",
                "room": {
                    "id": new_room.id,
                    "hotel_id": new_room.hotel_id,
                    "room_number": new_room.room_number,
                    "room_type": new_room.room_type,
                    "max_occupancy": new_room.max_occupancy,
                    "status": new_room.status
                }
            }), 201

        except Exception as e:
            session.rollback()
            print(f"Error creating room: {str(e)}")
            print(traceback.format_exc())
            return jsonify({"message": f"Fel vid skapande av rum: {str(e)}"}), 500


# DELETE: Ta bort rum
@app.delete('/rooms/<int:room_id>')
def delete_room(room_id):
    """Ta bort ett rum"""
    with Session() as session:
        try:
            # Kontrollera att rummet finns
            existing = session.execute(
                text("SELECT id, room_number, hotel_id FROM room WHERE id = :id"),
                {"id": room_id}
            ).fetchone()

            if not existing:
                return jsonify({"message": f"Rum med ID {room_id} finns inte."}), 404

            # Kontrollera om rummet har några bookingsegments
            booked = session.execute(
                text("SELECT id FROM bookingsegment WHERE room_id = :room_id"),
                {"room_id": room_id}
            ).fetchone()

            if booked:
                # Om rummet har historiska bokningar, ändra status istället
                session.execute(
                    text("UPDATE room SET status = 'inactive' WHERE id = :id"),
                    {"id": room_id}
                )
                session.commit()
                return jsonify({
                    "message": f"Rum {room_id} har historiska bokningar. Status ändrad till 'inactive'.",
                    "room": {
                        "id": room_id,
                        "status": "inactive"
                    }
                }), 200
            else:
                # Ta bort rummet om inga bokningar finns
                session.execute(
                    text("DELETE FROM room WHERE id = :id"),
                    {"id": room_id}
                )
                session.commit()

                return jsonify({
                    "message": f"Rum {room_id} borttaget.",
                    "deleted_room": {
                        "id": room_id,
                        "room_number": existing.room_number,
                        "hotel_id": existing.hotel_id
                    }
                }), 200

        except Exception as e:
            session.rollback()
            return jsonify({"message": f"Fel vid borttagning av rum: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)