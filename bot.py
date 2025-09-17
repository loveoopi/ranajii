import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
import logging
from pytgcalls import GroupCallFactory  # From py-tgcalls
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

# Get configuration from environment variables (Heroku)
API_ID = int(os.environ.get("API_ID", 22532815))
API_HASH = os.environ.get("API_HASH", "cdc905788c22458df1276e488c6d19b2")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8497303111:AAGKfmzGQH1v6DQHeBOecLqRL9mtq0dPtpg")
SESSION_STRING = os.environ.get("SESSION_STRING", "BQCOaU4AmT6YuACJAbzEOiO6wFhCLYkIFe4ULqDfvKY_YOBouB1n5CQm6OG6-yYu0QkSv1X2QTt39hzsJSZIgGPTl2vJVYuojvTNeByxFII5VvG0XHBkyHbVMSZLuHf2-IdUwl6pNE9EKFzra5tLJ86a2MJbLYeBdlpU1Ij-GIRFuN7f1COyfaTywncylNnvtHFonDbM7SaVwPpkZeAt6v451u_4l03ozM9M4vTM2aTNFFsNqJfnNUXLVmAE2Ad7K3vy9vwhGqe_o8DCxSG0pRJpZEUIFcksD9-BP1SmlUwdZFlwwjr6NNtuLVMbb8-QfC_g0kCeyjebbYVFD2RYJxH1wnf16wAAAAHrrzhRAA")
OWNER_ID = int(os.environ.get("OWNER_ID", 7406389785))
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb+srv://yacan69355:Cw92BrnfAfWQcLvU@cluster0.jh6h6wg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Initialize MongoDB client
try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client.telegram_vc_bot
    playlists = db.playlists
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    class DummyCollection:
        def find_one(self, *args, **kwargs): return None
        def update_one(self, *args, **kwargs): pass
        def find(self, *args, **kwargs): return []
    playlists = DummyCollection()

# Initialize clients
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_client = Client(
    SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH
)

# Initialize PyTgCalls with GroupCallFactory
call_py = GroupCallFactory(user_client, GroupCallFactory.MTC_MODE_FILE).get_group_call()

# Queue for videos
video_queue = []

# Current playing status
current_chat_id = None
is_playing = False

async def on_stream_end():
    global is_playing, video_queue
    if video_queue:
        video_queue.pop(0)
        if video_queue:
            await play_next_video()
        else:
            is_playing = False
    else:
        is_playing = False

async def play_next_video():
    global is_playing, current_chat_id
    if not video_queue:
        return
    video_info = video_queue[0]
    chat_id = video_info["chat_id"]
    file_path = video_info["file_path"]
    try:
        # Use file path directly; py-tgcalls handles audio/video
        await call_py.join(
            chat_id,
            input_filename=file_path
        )
        is_playing = True
        current_chat_id = chat_id
        await app.send_message(chat_id, f"▶️ Now playing: {video_info.get('title', 'Video')}")
    except Exception as e:
        print(f"Error playing video: {e}")
        video_queue.pop(0)
        await play_next_video()

@app.on_message(filters.command("vplay") & filters.group)
async def vplay_command(client: Client, message: Message):
    global video_queue, is_playing
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply_text("Please reply to a video with /vplay command.")
        return
    video = message.reply_to_message.video
    chat_id = message.chat.id
    await message.reply_text("📥 Downloading video...")
    file_path = await message.reply_to_message.download()
    video_info = {
        "chat_id": chat_id,
        "file_path": file_path,
        "message_id": message.reply_to_message.id,
        "title": video.file_name or f"Video {video.file_id}",
        "user_id": message.from_user.id
    }
    video_queue.append(video_info)
    queue_position = len(video_queue)
    await message.reply_text(f"✅ Video added to queue at position {queue_position}!")
    if not is_playing:
        await play_next_video()

@app.on_message(filters.command("skip") & filters.group)
async def skip_command(client: Client, message: Message):
    global is_playing
    if not is_playing:
        await message.reply_text("No video is currently playing.")
        return
    await call_py.stop()
    is_playing = False
    if video_queue:
        skipped_video = video_queue.pop(0)
        await message.reply_text("⏭️ Skipped current video.")
        if video_queue:
            await play_next_video()
    else:
        await message.reply_text("No more videos in queue.")

@app.on_message(filters.command("stop") & filters.group)
async def stop_command(client: Client, message: Message):
    global is_playing, video_queue
    if not is_playing:
        await message.reply_text("No video is currently playing.")
        return
    await call_py.stop()
    video_queue = []
    is_playing = False
    await message.reply_text("⏹️ Stopped playback and cleared queue.")

@app.on_message(filters.command("queue") & filters.group)
async def queue_command(client: Client, message: Message):
    if not video_queue:
        await message.reply_text("Queue is empty.")
        return
    queue_text = "📋 Current queue:\n"
    for i, video in enumerate(video_queue):
        queue_text += f"{i+1}. {video.get('title', 'Video')}\n"
    await message.reply_text(queue_text)

@app.on_message(filters.command("pause") & filters.group)
async def pause_command(client: Client, message: Message):
    if not is_playing:
        await message.reply_text("No video is currently playing.")
        return
    try:
        await call_py.pause()
        await message.reply_text("⏸️ Playback paused.")
    except Exception as e:
        await message.reply_text(f"Error pausing playback: {e}")

@app.on_message(filters.command("resume") & filters.group)
async def resume_command(client: Client, message: Message):
    if not is_playing:
        await message.reply_text("No video is currently playing.")
        return
    try:
        await call_py.resume()
        await message.reply_text("▶️ Playback resumed.")
    except Exception as e:
        await message.reply_text(f"Error resuming playback: {e}")

@app.on_message(filters.command("save") & filters.group)
async def save_playlist_command(client: Client, message: Message):
    if not video_queue:
        await message.reply_text("No videos in queue to save.")
        return
    if len(message.command) < 2:
        await message.reply_text("Please provide a name for the playlist. Usage: /save <playlist_name>")
        return
    playlist_name = message.command[1]
    user_id = message.from_user.id
    playlist_data = {
        "user_id": user_id,
        "name": playlist_name,
        "videos": video_queue,
        "chat_id": message.chat.id
    }
    playlists.update_one(
        {"user_id": user_id, "name": playlist_name},
        {"$set": playlist_data},
        upsert=True
    )
    await message.reply_text(f"✅ Playlist '{playlist_name}' saved with {len(video_queue)} videos.")

@app.on_message(filters.command("load") & filters.group)
async def load_playlist_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Please provide a playlist name. Usage: /load <playlist_name>")
        return
    playlist_name = message.command[1]
    user_id = message.from_user.id
    playlist = playlists.find_one({"user_id": user_id, "name": playlist_name})
    if not playlist:
        await message.reply_text(f"Playlist '{playlist_name}' not found.")
        return
    global video_queue
    video_queue.extend(playlist["videos"])
    await message.reply_text(f"✅ Playlist '{playlist_name}' loaded with {len(playlist['videos'])} videos.")
    if not is_playing and video_queue:
        await play_next_video()

@app.on_message(filters.command("list") & filters.group)
async def list_playlists_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_playlists = list(playlists.find({"user_id": user_id}))
    if not user_playlists:
        await message.reply_text("You don't have any saved playlists.")
        return
    playlist_list = "📋 Your playlists:\n"
    for playlist in user_playlists:
        playlist_list += f"• {playlist['name']} ({len(playlist['videos'])} videos)\n"
    await message.reply_text(playlist_list)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "🤖 **Telegram VC Video Bot**\n\n"
        "I can play videos in Telegram group voice chats!\n\n"
        "**Commands:**\n"
        "/vplay (reply to a video) - Add video to queue\n"
        "/skip - Skip current video\n"
        "/stop - Stop playback\n"
        "/pause - Pause playback\n"
        "/resume - Resume playback\n"
        "/queue - Show current queue\n"
        "/save <name> - Save queue as playlist\n"
        "/load <name> - Load a playlist\n"
        "/list - List your playlists\n\n"
        "Add me to a group and make me admin to get started!"
    )

async def main():
    await app.start()
    print("Bot started!")
    await user_client.start()
    print("User client started!")
    await call_py.start()
    print("PyTgCalls started!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
