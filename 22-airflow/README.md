# Положение МКС: API → Airflow → PostgreSQL

ДЗ занятия 22. DAG `iss_position_to_postgres`: три отдельных task `fetch → parse → load`, расписание каждые 30 минут, catchup=False, retries=2. Источник из условия: http://api.open-notify.org/iss-now.json. URL можно изменить через ISS_API_URL, чтобы подставить локальный тестовый API. На 17.10.2026 исходный endpoint ответил message=success.

Проверяется HTTP-ответ, статус API, свежесть timestamp (10 минут), диапазоны координат. В PostgreSQL сохраняется реальное время наблюдения, а не логическая дата Airflow. Запрос параметризован; PK по observed_at делает повторную загрузку одной точки идемпотентной. Хранятся время получения, run_id и границы периода, чтобы подтвердить разные запуски. Догонять прошлое текущими координатами нельзя: API не исторический.

## Локальный стенд

Скачанный `docker-compose.official.yaml` — официальный quickstart Apache Airflow 2.10.5, для обучения. Он запускает Airflow и служебный PostgreSQL; последний не подменяет требуемую облачную managed СУБД analytics.

```powershell
New-Item -ItemType Directory -Force dags,logs,plugins,config
docker compose -f docker-compose.official.yaml up airflow-init
docker compose -f docker-compose.official.yaml up -d
docker compose -f docker-compose.official.yaml exec airflow-scheduler airflow dags list-import-errors
```

UI: http://localhost:8080, учебный логин airflow / airflow. Не открывать этот учебный стенд в интернет с такими параметрами.

В UI Admin → Connections создать Connection Id `analytics_pg`, тип Postgres, host/port/db/login/password целевой БД. Для облака: БД analytics, private network/SSH-туннель или ограниченный доступ, TLS с проверкой сертификата согласно параметрам managed PostgreSQL. Секреты не класть в код или Git. Для локальной проверки можно использовать отдельную учебную PostgreSQL с базой analytics, доступную из сети Compose.

Включить DAG в UI. Дождаться более пяти реальных получасовых запусков (минимум шесть). Проверка:

```sql
SELECT observed_at,latitude,longitude,collected_at,dag_run_id,
       data_interval_start,data_interval_end
FROM iss_observations ORDER BY observed_at;
SELECT count(DISTINCT data_interval_start) AS periods FROM iss_observations;
```

## Облачное развёртывание и статус

17.10.2026 Airflow на VM Yandex Cloud записал в managed PostgreSQL 11 наблюдений за 11 разных получасовых периодов. Последнее наблюдение в экспорте: 16:30:05 UTC (18:30:05 Europe/Berlin). Результат подтверждён запросом в WebSQL облачной базы analytics и скриншотом cloud-periods-websql.png. Локальные данные в облачную таблицу не переносились.

```sql
SELECT count(*) AS observations,
       count(DISTINCT data_interval_start) AS periods,
       max(observed_at) AS last_observation
FROM public.iss_observations;
```

Результат: observations=11, periods=11, last_observation=2026-10-17 19:30:05+03. Экспорт WebSQL: cloud-observations.json. Скриншот cloud-periods-websql.png фиксирует более раннюю проверку 8 периодов.

![Ранее подтверждённые восемь облачных периодов в WebSQL](cloud-periods-websql.png)

17.10.2026 решение отправлено в OTUS на проверку (карточка 49299). Ручная резервная копия PostgreSQL завершилась успешно; затем VM и managed PostgreSQL штатно остановлены, оба статуса Stopped подтверждены в консоли. Данные и диски сохранены для обучения. SSH с рабочего компьютера был недоступен; это не помешало DAG собирать данные.
[Официальный Docker quickstart Airflow 2.10.5](https://airflow.apache.org/docs/apache-airflow/2.10.5/howto/docker-compose/index.html).

## Проверенный локальный запуск 17.10.2026

Для текущего стенда используется docker-compose.local.yml: один Airflow standalone на localhost:8080 и analytics в локальном PostgreSQL сети otus-weather_default. Connection URI хранится только в .env. DAG без import errors. Получены два реальных успешных запуска (scheduled и manual), в БД сохранены две точки МКС с разными observed_at. Это один получасовой data_interval и не заменяет требование >5 периодов в облаке. Скриншот локального Airflow — local-runs.png; фактический вывод БД и списка runs — local-verification.txt. Оба запуска обращались к настоящему API, данные не синтезировались.

Файл iss_pipeline.py в корне — копия для публикации; для официального Compose скопировать его в dags/iss_pipeline.py. Для локального Compose нужен предварительно запущенный PostgreSQL и созданная analytics; этот стенд предназначен только для локальной проверки.


![Локальные успешные запуски](local-runs.png)


## Повторная локальная проверка

17.10.2026, последнее наблюдение 10:30:09 UTC: 9 строк за 8 разных получасовых периодов, failed DAG runs отсутствуют. Облачные запуски этим не подтверждаются. Для будущей VM добавлен docker-compose.cloud.yml: подключение analytics_pg нужно создать через UI, сертификат managed PostgreSQL монтируется из certs. SQL проверки — verify-cloud.sql. Конфигурация Compose проверена командой config --quiet без запуска ресурсов.

## Созданный облачный стенд

Ubuntu24.04,2vCPU8ГБRAM,HDD20ГБ,Airflow2.10.5 standalone в Docker; отдельный managed PostgreSQL17.11Yandex,1хостb2.medium,network-hdd10ГБ,БДanalytics. Метаданные самого Airflow — SQLite/SequentialExecutor, допустимые здесь только для учебного стенда. Данные МКС идут исключительно в managed PostgreSQL, не в контейнер BI.

Использован docker-compose.cloud.yml. В UI Admin → Connections:analytics_pg,типPostgres,порт6432,databaseanalytics;Extra sslmode=verify-full и sslrootcert=/opt/airflow/certs/YandexInternalRootCA.crt. Пароли и ключи в репозиторий не входят. Веб-порт8080 слушает толькоloopbackVM,доступ черезSSH-туннель.

После проверки оба облачных ресурса остановлены без удаления данных. Для обучения их можно запустить снова; публичный IP VM динамический и при следующем запуске изменится.
