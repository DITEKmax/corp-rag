package com.corprag.adapter.amqp;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.config.AmqpConfig;
import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.contracts.constants.QueueNames;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.ApplicationContext;

class AmqpConfigTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(AmqpConfig.class);

    @Test
    void declaresDocumentExchangeQueuesDlqsAndBindingsFromGeneratedConstants() {
        contextRunner.run(context -> {
            TopicExchange documentsExchange = context.getBean("documentsTopicExchange", TopicExchange.class);
            TopicExchange deadLetterExchange = context.getBean("documentsDeadLetterExchange", TopicExchange.class);
            assertThat(documentsExchange.getName()).isEqualTo(ExchangeNames.DOCUMENTS_TOPIC);
            assertThat(documentsExchange.isDurable()).isTrue();
            assertThat(deadLetterExchange.getName()).isEqualTo(ExchangeNames.DOCUMENTS_DLX);
            assertThat(deadLetterExchange.isDurable()).isTrue();

            assertPrimaryQueue(context, "aiDocumentUploadedQueue",
                    QueueNames.AI_DOCUMENT_UPLOADED, QueueNames.AI_DOCUMENT_UPLOADED_DLQ);
            assertPrimaryQueue(context, "aiDocumentDeletedQueue",
                    QueueNames.AI_DOCUMENT_DELETED, QueueNames.AI_DOCUMENT_DELETED_DLQ);
            assertPrimaryQueue(context, "backendDocumentIndexedQueue",
                    QueueNames.BACKEND_DOCUMENT_INDEXED, QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ);
            assertPrimaryQueue(context, "backendDocumentFailedQueue",
                    QueueNames.BACKEND_DOCUMENT_FAILED, QueueNames.BACKEND_DOCUMENT_FAILED_DLQ);

            assertQueue(context, "aiDocumentUploadedDeadLetterQueue", QueueNames.AI_DOCUMENT_UPLOADED_DLQ);
            assertQueue(context, "aiDocumentDeletedDeadLetterQueue", QueueNames.AI_DOCUMENT_DELETED_DLQ);
            assertQueue(context, "backendDocumentIndexedDeadLetterQueue", QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ);
            assertQueue(context, "backendDocumentFailedDeadLetterQueue", QueueNames.BACKEND_DOCUMENT_FAILED_DLQ);

            assertBinding(context, "aiDocumentUploadedBinding",
                    QueueNames.AI_DOCUMENT_UPLOADED, ExchangeNames.DOCUMENTS_TOPIC, EventRoutingKeys.DOCUMENT_UPLOADED);
            assertBinding(context, "aiDocumentDeletedBinding",
                    QueueNames.AI_DOCUMENT_DELETED, ExchangeNames.DOCUMENTS_TOPIC, EventRoutingKeys.DOCUMENT_DELETED);
            assertBinding(context, "backendDocumentIndexedBinding",
                    QueueNames.BACKEND_DOCUMENT_INDEXED, ExchangeNames.DOCUMENTS_TOPIC, EventRoutingKeys.DOCUMENT_INDEXED);
            assertBinding(context, "backendDocumentFailedBinding",
                    QueueNames.BACKEND_DOCUMENT_FAILED, ExchangeNames.DOCUMENTS_TOPIC,
                    EventRoutingKeys.DOCUMENT_INDEXING_FAILED);

            assertBinding(context, "aiDocumentUploadedDeadLetterBinding",
                    QueueNames.AI_DOCUMENT_UPLOADED_DLQ, ExchangeNames.DOCUMENTS_DLX,
                    QueueNames.AI_DOCUMENT_UPLOADED_DLQ);
            assertBinding(context, "aiDocumentDeletedDeadLetterBinding",
                    QueueNames.AI_DOCUMENT_DELETED_DLQ, ExchangeNames.DOCUMENTS_DLX,
                    QueueNames.AI_DOCUMENT_DELETED_DLQ);
            assertBinding(context, "backendDocumentIndexedDeadLetterBinding",
                    QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ, ExchangeNames.DOCUMENTS_DLX,
                    QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ);
            assertBinding(context, "backendDocumentFailedDeadLetterBinding",
                    QueueNames.BACKEND_DOCUMENT_FAILED_DLQ, ExchangeNames.DOCUMENTS_DLX,
                    QueueNames.BACKEND_DOCUMENT_FAILED_DLQ);
        });
    }

    private static void assertPrimaryQueue(
            ApplicationContext context,
            String beanName,
            String queueName,
            String deadLetterQueueName) {
        Queue queue = assertQueue(context, beanName, queueName);
        assertThat(queue.getArguments())
                .containsEntry("x-dead-letter-exchange", ExchangeNames.DOCUMENTS_DLX)
                .containsEntry("x-dead-letter-routing-key", deadLetterQueueName);
    }

    private static Queue assertQueue(ApplicationContext context, String beanName, String queueName) {
        Queue queue = context.getBean(beanName, Queue.class);
        assertThat(queue.getName()).isEqualTo(queueName);
        assertThat(queue.isDurable()).isTrue();
        return queue;
    }

    private static void assertBinding(
            ApplicationContext context,
            String beanName,
            String destination,
            String exchange,
            String routingKey) {
        Binding binding = context.getBean(beanName, Binding.class);
        assertThat(binding.getDestination()).isEqualTo(destination);
        assertThat(binding.getExchange()).isEqualTo(exchange);
        assertThat(binding.getRoutingKey()).isEqualTo(routingKey);
    }
}
