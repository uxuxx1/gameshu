import asyncio
import json
import uuid

rooms = {}
random_queue = []

def generate_code():
    return str(uuid.uuid4().int)[:4]

async def handle_client(reader, writer):
    player_id = str(uuid.uuid4())
    room_code = None
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            message = data.decode().strip()
            try:
                msg = json.loads(message)
            except:
                continue
            msg_type = msg.get("type")

            if msg_type == "join_random":
                if random_queue:
                    opponent_writer = random_queue.pop()
                    room_code = generate_code()
                    rooms[room_code] = {
                        "players": {player_id: writer, "opponent": opponent_writer},
                        "state": {
                            "positions": {},
                            "health": {player_id: 100, "opponent": 100},
                            "ammo": {player_id: 30, "opponent": 30}
                        }
                    }
                    await send(writer, "room_created", {"room": room_code, "player_id": player_id})
                    await send(opponent_writer, "room_joined", {"room": room_code, "player_id": "opponent"})
                else:
                    random_queue.append(writer)
                    await send(writer, "waiting", {"message": "Ожидание противника..."})

            elif msg_type == "create_room":
                room_code = generate_code()
                rooms[room_code] = {
                    "players": {player_id: writer},
                    "state": {
                        "positions": {},
                        "health": {player_id: 100},
                        "ammo": {player_id: 30}
                    }
                }
                await send(writer, "room_created", {"room": room_code, "player_id": player_id})

            elif msg_type == "join_room":
                code = msg.get("code")
                if code in rooms and len(rooms[code]["players"]) == 1:
                    room = rooms[code]
                    opponent_id = list(room["players"].keys())[0]
                    room["players"][player_id] = writer
                    room["state"]["health"][player_id] = 100
                    room["state"]["ammo"][player_id] = 30
                    room_code = code
                    await send(writer, "room_joined", {"room": code, "player_id": player_id})
                    await send(room["players"][opponent_id], "opponent_joined", {"player_id": player_id})
                else:
                    await send(writer, "error", {"message": "Неверный код или комната занята"})

            elif msg_type == "game_update":
                if room_code and room_code in rooms:
                    room = rooms[room_code]
                    room["state"]["positions"][player_id] = msg.get("position")
                    room["state"]["health"][player_id] = msg.get("health")
                    room["state"]["ammo"][player_id] = msg.get("ammo")
                    for pid, ws in room["players"].items():
                        if pid != player_id:
                            await send(ws, "opponent_update", {
                                "position": room["state"]["positions"].get(pid),
                                "health": room["state"]["health"].get(pid),
                                "ammo": room["state"]["ammo"].get(pid)
                            })

            elif msg_type == "shot":
                if room_code and room_code in rooms:
                    room = rooms[room_code]
                    for pid in room["players"]:
                        if pid != player_id:
                            new_hp = room["state"]["health"].get(pid, 100) - 10
                            room["state"]["health"][pid] = max(0, new_hp)
                            await send(room["players"][pid], "damage", {"health": new_hp})

    except Exception as e:
        print("Error:", e)
    finally:
        if room_code and room_code in rooms:
            room = rooms[room_code]
            if player_id in room["players"]:
                del room["players"][player_id]
                if not room["players"]:
                    del rooms[room_code]
        if writer in random_queue:
            random_queue.remove(writer)
        writer.close()
        await writer.wait_closed()

async def send(writer, type, data):
    try:
        msg = json.dumps({"type": type, **data}) + "\n"
        writer.write(msg.encode())
        await writer.drain()
    except:
        pass

async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 8765)
    print("Сервер запущен на порту 8765")
    async with server:
        await server.serve_forever()

asyncio.run(main())
