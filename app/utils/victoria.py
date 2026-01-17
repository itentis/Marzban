import requests
from config import VICTORIAMETRICS_BATCH_SIZE as BATCH_SIZE
from config import VICTORIAMETRICS_CONNSTRING as URL
from config import HOSTNAME
from config import VICTORIAMETRICS_DEBUG

# Global variable for batch storage
batch_storage = []


def send_batch(batch):
    concat = "\n".join(batch)
    if VICTORIAMETRICS_DEBUG:
        print(concat)
    response = requests.post(URL,
                             data=concat,
                             headers={"Content-Type": "text/plain"})
    if response.status_code == 200:
        print("Batch data sent successfully!")
    else:
        print(f"Error sending data: {response.status_code}, {response.text}")


def queue_and_send(record):
    # prep the record
    batch_storage.append(
        f'marzban_user_{record.link}{{user_id="{record.name.split(".")[1]}", instance="{HOSTNAME}"}} {record.value}'
    )
    # Check if we've reached the batch size
    if len(batch_storage) >= BATCH_SIZE:
        # Take a snapshot of the current batch
        current_batch = batch_storage[:BATCH_SIZE]
        # Remove the sent batch from the storage
        batch_storage[:] = batch_storage[BATCH_SIZE:]
        # Send the current batch synchronously
        send_batch(current_batch)
