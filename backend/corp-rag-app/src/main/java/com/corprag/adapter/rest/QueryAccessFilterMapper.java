package com.corprag.adapter.rest;

import com.corprag.contracts.ai.v1.model.AccessFilter;
import com.corprag.domain.ResolvedAccessFilter;
import org.springframework.stereotype.Component;

@Component
public class QueryAccessFilterMapper {

    public AccessFilter toContract(ResolvedAccessFilter filter) {
        return new AccessFilter()
                .accessLevels(filter.accessLevels().stream()
                        .map(level -> com.corprag.contracts.ai.v1.model.AccessLevel.fromValue(level.name()))
                        .toList())
                .departments(filter.departments())
                .docTypes(filter.docTypes().stream()
                        .map(docType -> com.corprag.contracts.ai.v1.model.DocType.fromValue(docType.name()))
                        .toList());
    }
}
