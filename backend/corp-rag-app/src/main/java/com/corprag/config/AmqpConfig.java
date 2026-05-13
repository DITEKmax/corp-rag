package com.corprag.config;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.contracts.constants.QueueNames;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

@Configuration
@EnableScheduling
public class AmqpConfig {

    @Bean
    TopicExchange documentsTopicExchange() {
        return new TopicExchange(ExchangeNames.DOCUMENTS_TOPIC, true, false);
    }

    @Bean
    TopicExchange documentsDeadLetterExchange() {
        return new TopicExchange(ExchangeNames.DOCUMENTS_DLX, true, false);
    }

    @Bean
    Queue aiDocumentUploadedQueue() {
        return primaryQueue(QueueNames.AI_DOCUMENT_UPLOADED, QueueNames.AI_DOCUMENT_UPLOADED_DLQ);
    }

    @Bean
    Queue aiDocumentUploadedDeadLetterQueue() {
        return QueueBuilder.durable(QueueNames.AI_DOCUMENT_UPLOADED_DLQ).build();
    }

    @Bean
    Binding aiDocumentUploadedBinding(
            @Qualifier("aiDocumentUploadedQueue") Queue aiDocumentUploadedQueue,
            @Qualifier("documentsTopicExchange") TopicExchange documentsTopicExchange) {
        return BindingBuilder.bind(aiDocumentUploadedQueue)
                .to(documentsTopicExchange)
                .with(EventRoutingKeys.DOCUMENT_UPLOADED);
    }

    @Bean
    Binding aiDocumentUploadedDeadLetterBinding(
            @Qualifier("aiDocumentUploadedDeadLetterQueue") Queue aiDocumentUploadedDeadLetterQueue,
            @Qualifier("documentsDeadLetterExchange") TopicExchange documentsDeadLetterExchange) {
        return BindingBuilder.bind(aiDocumentUploadedDeadLetterQueue)
                .to(documentsDeadLetterExchange)
                .with(QueueNames.AI_DOCUMENT_UPLOADED_DLQ);
    }

    @Bean
    Queue aiDocumentDeletedQueue() {
        return primaryQueue(QueueNames.AI_DOCUMENT_DELETED, QueueNames.AI_DOCUMENT_DELETED_DLQ);
    }

    @Bean
    Queue aiDocumentDeletedDeadLetterQueue() {
        return QueueBuilder.durable(QueueNames.AI_DOCUMENT_DELETED_DLQ).build();
    }

    @Bean
    Binding aiDocumentDeletedBinding(
            @Qualifier("aiDocumentDeletedQueue") Queue aiDocumentDeletedQueue,
            @Qualifier("documentsTopicExchange") TopicExchange documentsTopicExchange) {
        return BindingBuilder.bind(aiDocumentDeletedQueue)
                .to(documentsTopicExchange)
                .with(EventRoutingKeys.DOCUMENT_DELETED);
    }

    @Bean
    Binding aiDocumentDeletedDeadLetterBinding(
            @Qualifier("aiDocumentDeletedDeadLetterQueue") Queue aiDocumentDeletedDeadLetterQueue,
            @Qualifier("documentsDeadLetterExchange") TopicExchange documentsDeadLetterExchange) {
        return BindingBuilder.bind(aiDocumentDeletedDeadLetterQueue)
                .to(documentsDeadLetterExchange)
                .with(QueueNames.AI_DOCUMENT_DELETED_DLQ);
    }

    @Bean
    Queue backendDocumentIndexedQueue() {
        return primaryQueue(QueueNames.BACKEND_DOCUMENT_INDEXED, QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ);
    }

    @Bean
    Queue backendDocumentIndexedDeadLetterQueue() {
        return QueueBuilder.durable(QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ).build();
    }

    @Bean
    Binding backendDocumentIndexedBinding(
            @Qualifier("backendDocumentIndexedQueue") Queue backendDocumentIndexedQueue,
            @Qualifier("documentsTopicExchange") TopicExchange documentsTopicExchange) {
        return BindingBuilder.bind(backendDocumentIndexedQueue)
                .to(documentsTopicExchange)
                .with(EventRoutingKeys.DOCUMENT_INDEXED);
    }

    @Bean
    Binding backendDocumentIndexedDeadLetterBinding(
            @Qualifier("backendDocumentIndexedDeadLetterQueue") Queue backendDocumentIndexedDeadLetterQueue,
            @Qualifier("documentsDeadLetterExchange") TopicExchange documentsDeadLetterExchange) {
        return BindingBuilder.bind(backendDocumentIndexedDeadLetterQueue)
                .to(documentsDeadLetterExchange)
                .with(QueueNames.BACKEND_DOCUMENT_INDEXED_DLQ);
    }

    @Bean
    Queue backendDocumentFailedQueue() {
        return primaryQueue(QueueNames.BACKEND_DOCUMENT_FAILED, QueueNames.BACKEND_DOCUMENT_FAILED_DLQ);
    }

    @Bean
    Queue backendDocumentFailedDeadLetterQueue() {
        return QueueBuilder.durable(QueueNames.BACKEND_DOCUMENT_FAILED_DLQ).build();
    }

    @Bean
    Binding backendDocumentFailedBinding(
            @Qualifier("backendDocumentFailedQueue") Queue backendDocumentFailedQueue,
            @Qualifier("documentsTopicExchange") TopicExchange documentsTopicExchange) {
        return BindingBuilder.bind(backendDocumentFailedQueue)
                .to(documentsTopicExchange)
                .with(EventRoutingKeys.DOCUMENT_INDEXING_FAILED);
    }

    @Bean
    Binding backendDocumentFailedDeadLetterBinding(
            @Qualifier("backendDocumentFailedDeadLetterQueue") Queue backendDocumentFailedDeadLetterQueue,
            @Qualifier("documentsDeadLetterExchange") TopicExchange documentsDeadLetterExchange) {
        return BindingBuilder.bind(backendDocumentFailedDeadLetterQueue)
                .to(documentsDeadLetterExchange)
                .with(QueueNames.BACKEND_DOCUMENT_FAILED_DLQ);
    }

    private static Queue primaryQueue(String queueName, String deadLetterQueueName) {
        return QueueBuilder.durable(queueName)
                .deadLetterExchange(ExchangeNames.DOCUMENTS_DLX)
                .deadLetterRoutingKey(deadLetterQueueName)
                .build();
    }
}
