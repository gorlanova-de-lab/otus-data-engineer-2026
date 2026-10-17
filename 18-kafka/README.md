# Kafka в Docker

ДЗ OTUS, занятие 18. Один сервер `apache/kafka:4.1.2` в режиме KRaft (broker + controller), без ZooKeeper. Сервис слушает только localhost; это учебная конфигурация без TLS/SASL. Образ: [Apache Kafka Docker](https://kafka.apache.org/41/getting-started/docker/).

## Повторить запуск

Команды PowerShell выполняются из папки с `docker-compose.yml`:

```powershell
docker compose up -d
docker compose ps
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Если брокер ещё стартует, повторить последнюю команду после появления healthy в `docker compose ps`.

```powershell
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic test --partitions 1 --replication-factor 1
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic test
@('first message','second message','third message') | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic test
docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic test --from-beginning --max-messages 3 --timeout-ms 20000
```

`test` — топик, одна partition хранит упорядоченную последовательность сообщений, replication-factor=1 означает одну копию данных. Producer записывает строки, consumer читает их с начала. Контроллер управляет метаданными, брокер хранит сообщения. Для одного сервера внутренние replication-factor/min-ISR выставлены в 1.

## Фактическая проверка 17.10.2026

```text
Created topic test.
Topic: test PartitionCount: 1 ReplicationFactor: 1
Partition: 0 Leader: 1 Replicas: 1 Isr: 1
first message
second message
third message
Processed a total of 3 messages
```

Все обязательные шаги выполнены. Бонус с тремя серверами не выполнялся.

Повторная отправка добавляет новые сообщения. Команда consumer выше читает первые три, а не обязательно последние. Для нового опыта можно выбрать другое имя топика. `docker compose stop` останавливает с сохранением контейнера; `docker compose start` продолжает. Данные в этой минимальной конфигурации находятся внутри контейнера: его удаление через `docker compose down` уничтожит их.
