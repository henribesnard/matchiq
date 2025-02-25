from confluent_kafka import Consumer, KafkaError
from django.apps import apps
import json
from .transformer import RDFTransformer

class CDCConsumer:
    def __init__(self, bootstrap_servers, group_id, topics):
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(topics)
        self.transformer = RDFTransformer()
        self.buffer = []
        self.buffer_size = 1000

    def process_message(self, message):
        try:
            data = json.loads(message.value())
            table_name = data['source']['table']
            operation = data['op']

            # Get the Django model
            model = apps.get_model('your_app', table_name)
            
            if operation in ['c', 'u']:  # Create or Update
                instance = model.objects.get(id=data['payload']['id'])
                self.buffer.append({
                    'operation': operation,
                    'instance': instance,
                    'model': model
                })
            elif operation == 'd':  # Delete
                # Handle deletion in RDF graph
                pass

            if len(self.buffer) >= self.buffer_size:
                self.process_buffer()

        except Exception as e:
            print(f"Error processing message: {e}")

    def process_buffer(self):
        try:
            for change in self.buffer:
                if change['operation'] in ['c', 'u']:
                    self.transformer.transform_instance(change['instance'])
            self.buffer = []
        except Exception as e:
            print(f"Error processing buffer: {e}")
            self.buffer = []

    def run(self):
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    print(f"Consumer error: {msg.error()}")
                    continue

                self.process_message(msg)
        finally:
            self.consumer.close()

# Example usage
# from rdf_transform.consumer import CDCConsumer
# from rdf_transform.transformer import RDFTransformer

def main():
    # Initialize CDC consumer
    cdc_consumer = CDCConsumer(
        bootstrap_servers='localhost:9092',
        group_id='football-rdf-group',
        topics=['dbserver1.public.country', 'dbserver1.public.team']
    )

    # Run the consumer
    cdc_consumer.run()

if __name__ == "__main__":
    main()