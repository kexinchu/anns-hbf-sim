"""Explicit FIFO fill order by default; legacy LRU is a labeled sensitivity option."""
edit('include/hbf_eventlab/architecture/execution_configuration.hpp','struct ExecutionConfiguration {',
 'struct ExecutionConfiguration {\n    bool cache_hit_recency=false; // false: fill-order FIFO; true: legacy LRU sensitivity')
edit('include/hbf_eventlab/runtime/bank_cache.hpp','public:\n    bool contains',
 'public:\n    explicit BankCache(bool hit_recency=false):hit_recency_(hit_recency) {}\n    bool contains')
edit('include/hbf_eventlab/runtime/bank_cache.hpp','private:\n    struct Slot',
 'private:\n    bool hit_recency_;\n    struct Slot')
edit('src/runtime/bank_cache.cpp','    s.age=checked_add(age_,1); age_=s.age;\n    return ReadResultLease',
 '    if(hit_recency_) { s.age=checked_add(age_,1); age_=s.age; }\n    return ReadResultLease')
edit('src/runtime/device_driver.cpp','     egress_(description_.geometry().host_channels,config_.buffers.egress),',
 '     cache_(config_.cache_hit_recency),\n     egress_(description_.geometry().host_channels,config_.buffers.egress),')
edit('src/configuration/simulation_configuration.cpp','    add("execution.media_timing.sense_ps",e.media_timing.sense);',
 '    add("execution.cache_hit_recency",e.cache_hit_recency);\n    add("execution.media_timing.sense_ps",e.media_timing.sense);')
