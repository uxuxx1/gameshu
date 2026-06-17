import asyncio
import json
import uuid
import websockets

rooms = {}
random_queue = []

def generate_code():
    return str(uuid.uuid4().int)[:4]

async def handler(websocket, path):
    player_id = str(uuid.uuid4())
    room_code = None
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "join_random":
                if random_queue:
                    opponent_ws = random_queue.pop()
                    room_code = generate_code()
                    rooms[room_code] = {
                        "players": {player_id: websocket, "opponent": opponent_ws},
                        "state": {
                            "positions": {},
                            "health": {player_id: 100, "opponent": 100},
                            "ammo": {player_id: 30, "opponent": 30}
                        }
                    }
                    await notify(websocket, "room_created", {"room": room_code, "player_id": player_id})
                    await notify(opponent_ws, "room_joined", {"room": room_code, "player_id": "opponent"})
                else:
                    random_queue.append(websocket)
                    await notify(websocket, "waiting", {"message": "Ожидание противника..."})
            elif msg_type == "create_room":
                room_code = generate_code()
                rooms[room_code] = {
                    "players": {player_id: websocket},
                    "state": {
                        "positions": {},
                        "health": {player_id: 100},
                        "ammo": {player_id: 30}
                    }
                }
                await notify(websocket, "room_created", {"room": room_code, "player_id": player_id})
            elif msg_type == "join_room":
                code = data.get("code")
                if code in rooms and len(rooms[code]["players"]) == 1:
                    room = rooms[code]
                    opponent_id = list(room["players"].keys())[0]
                    room["players"][player_id] = websocket
                    room["state"]["health"][player_id] = 100
                    room["state"]["ammo"][player_id] = 30
                    room_code = code
                    await notify(websocket, "room_joined", {"room": code, "player_id": player_id})
                    await notify(room["players"][opponent_id], "opponent_joined", {"player_id": player_id})
                else:
                    await notify(websocket, "error", {"message": "Неверный код или комната занята"})
            elif msg_type == "game_update":
                if room_code and room_code in rooms:
                    room = rooms[room_code]
                    room["state"]["positions"][player_id] = data.get("position")
                    room["state"]["health"][player_id] = data.get("health")
                    room["state"]["ammo"][player_id] = data.get("ammo")
                    for pid, ws in room["players"].items():
                        if pid != player_id:
                            await notify(ws, "opponent_update", {
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
                            await notify(room["players"][pid], "damage", {"health": new_hp})
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if room_code and room_code in rooms:
            room = rooms[room_code]
            if player_id in room["players"]:
                del room["players"][player_id]
                if not room["players"]:
                    del rooms[room_code]
        if websocket in random_queue:
            random_queue.remove(websocket)

async def notify(websocket, type, data):
    try:
        await websocket.send(json.dumps({"type": type, **data}))
    except:
        pass

start_server = websockets.serve(handler, "0.0.0.0", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
