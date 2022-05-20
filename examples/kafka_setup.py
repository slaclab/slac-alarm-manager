from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import UnknownTopicOrPartitionError


def delete_topics(topic_name: str) -> None:
    """ Deletes the topics associated with the input name if they exist. """
    admin_client = KafkaAdminClient(bootstrap_servers='localhost:9092', client_id='test_data_admin_client')
    try:
        admin_client.delete_topics([topic_name, f'{topic_name}Command'])
    except UnknownTopicOrPartitionError:
        pass


def create_topics(topic_name: str) -> None:
    """ Create the state/config and command topic for the input name """
    admin_client = KafkaAdminClient(bootstrap_servers='localhost:9092', client_id='test_data_admin_client')

    topic_list = [NewTopic(name=topic_name, num_partitions=1, replication_factor=1),
                  NewTopic(name=f'{topic_name}Command', num_partitions=1, replication_factor=1)]

    admin_client.create_topics(new_topics=topic_list, validate_only=False)


def load_test_data(topic_name: str):
    """ Sends a sample alarm configuration and its associated data to kafka """
    kafka_producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                   value_serializer=lambda x: x.encode('utf-8'),
                                   key_serializer=lambda x: x.encode('utf-8'))
    with open('../fixed_config.txt', 'r') as f:
        tree_paths = f.readlines()

    for path in tree_paths:
        path = path.strip()
        kafka_producer.send(topic_name, key=f'config:{path}', value='{}')

    with open('../state_messages.txt', 'r') as f:
        state_messages = f.readlines()

    for message in state_messages:
        message = message.strip()
        print(f'Trying to send value: {message.split("++++")[1]} which has type {type(message.split("++++")[1])}')
        kafka_producer.send(topic_name, key=message.split('++++')[0], value=message.split('++++')[1])


delete_topics('ExampleTopic')
create_topics('ExampleTopic')
load_test_data('ExampleTopic')
