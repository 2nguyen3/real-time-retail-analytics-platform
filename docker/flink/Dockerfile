# syntax=docker/dockerfile:1.7
FROM flink:2.2.1-scala_2.12-java17

# Flink 2.2 SQL needs Kafka SQL, JDBC core, PostgreSQL connector and JDBC driver.
ADD --chmod=0644 --checksum=sha256:5605c691d11a501382c383fecba37a7a552467da5ab7ba904ef5d6f3d62c5616 https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/5.0.0-2.2/flink-sql-connector-kafka-5.0.0-2.2.jar /opt/flink/lib/flink-sql-connector-kafka-5.0.0-2.2.jar
ADD --chmod=0644 --checksum=sha256:f8357ab799095e6486315db4019edf63ced762bc8c2eaa63614c7b962755564b https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc-core/4.1.0-2.2/flink-connector-jdbc-core-4.1.0-2.2.jar /opt/flink/lib/flink-connector-jdbc-core-4.1.0-2.2.jar
ADD --chmod=0644 --checksum=sha256:ae6da5769d932123606f1b9e03d90d57cde9c1d0144df6ffa64a9701afb86d6b https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc-postgres/4.1.0-2.2/flink-connector-jdbc-postgres-4.1.0-2.2.jar /opt/flink/lib/flink-connector-jdbc-postgres-4.1.0-2.2.jar
ADD --chmod=0644 --checksum=sha256:2a32a9dcbc42d67a50ad3a0de5efd102c8d2be46720045f2cbd6689f160ab7c7 https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.8/postgresql-42.7.8.jar /opt/flink/lib/postgresql-42.7.8.jar
