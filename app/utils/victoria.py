import asyncio
import aiohttp
from config import VICTORIAMETRICS_BATCH_SIZE as BATCH_SIZE
from config import VICTORIAMETRICS_CONNSTRING as URL
from config import HOSTNAME

# Global variable for batch storage
batch_storage = []


async def send_batch(batch):
    concat = "\n".join(batch)
    async with aiohttp.ClientSession() as session:
        async with session.post(URL,
                                data=concat,
                                headers={"Content-Type": "text/plain"}
                                ) as response:
            if response.status == 200:
                print("Batch data sent successfully!")
            else:
                print(f"Error sending data: {response.status}, {await response.text()}")


class Queue:
    def __init__(self):
        self.lock = asyncio.Lock()  # Ensure thread-safe access to batch_storage

    async def queue_and_send(self, record):
        async with self.lock:  # Lock access to shared resource
            # prep the record
            batch_storage.append(f'marzban_user_{record.link}{{user_id="{record.name.split(".")[1]}", instance="{HOSTNAME}"}} {record.value}')
            # Check if we've reached the batch size
            if len(batch_storage) >= BATCH_SIZE:
                # Take a snapshot of the current batch
                current_batch = batch_storage[:BATCH_SIZE]
                # Remove the sent batch from the storage
                batch_storage[:] = batch_storage[BATCH_SIZE:]
                # Send the current batch asynchronously
                asyncio.create_task(send_batch(current_batch))


queue_instance = Queue()

# Update existing function call to use the singleton instance
def queue_and_send(record):
    asyncio.run(queue_instance.queue_and_send(record))
