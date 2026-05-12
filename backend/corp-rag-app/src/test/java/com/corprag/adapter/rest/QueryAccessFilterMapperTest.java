package com.corprag.adapter.rest;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.contracts.ai.v1.model.AccessFilter;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import java.util.List;
import org.junit.jupiter.api.Test;

class QueryAccessFilterMapperTest {

    private final QueryAccessFilterMapper mapper = new QueryAccessFilterMapper();

    @Test
    void mapsResolvedFilterToAiContractEnums() {
        AccessFilter filter = mapper.toContract(new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of("HR", "IT"),
                List.of(DocType.POLICY, DocType.REPORT)));

        assertThat(filter.getAccessLevels())
                .containsExactly(
                        com.corprag.contracts.ai.v1.model.AccessLevel.PUBLIC,
                        com.corprag.contracts.ai.v1.model.AccessLevel.INTERNAL);
        assertThat(filter.getDepartments()).containsExactly("HR", "IT");
        assertThat(filter.getDocTypes())
                .containsExactly(
                        com.corprag.contracts.ai.v1.model.DocType.POLICY,
                        com.corprag.contracts.ai.v1.model.DocType.REPORT);
    }
}
