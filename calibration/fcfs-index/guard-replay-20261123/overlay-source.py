"""Exact built-in FCFS selection using enqueue age; custom policies retain scan."""
edit('include/hbf_eventlab/host/host_driver.hpp',
 '        std::set<SendUnitId> queue;',
 '        std::set<SendUnitId> queue;\n        std::set<std::pair<std::uint64_t,SendUnitId>> age_queue;')
edit('include/hbf_eventlab/host/host_driver.hpp','    void enqueue(Unit&,Tick);',
 '''    void erase_queued(Unit& u) {
        auto& ch=channels_[u.fragments.front().address.channel];
        ch.queue.erase(u.id);ch.age_queue.erase({u.enqueue_sequence,u.id});
    }
    void enqueue(Unit&,Tick);''')
edit('src/host/host_driver.cpp',
 '    next_enqueue_=checked_add(next_enqueue_,1);',
 '''    auto& age=channels_[u.fragments.front().address.channel].age_queue;
    age.erase({u.enqueue_sequence,u.id});
    next_enqueue_=checked_add(next_enqueue_,1);''')
edit('src/host/host_driver.cpp',
 '    u.enqueue_sequence=next_enqueue_;u.queued_at=at;',
 '    u.enqueue_sequence=next_enqueue_;u.queued_at=at;\n    age.insert({u.enqueue_sequence,u.id});')
edit('src/host/host_driver.cpp','u.stage=UnitStage::Handed;channel.queue.erase(chosen);','u.stage=UnitStage::Handed;erase_queued(u);')
edit('src/host/host_driver.cpp','channels_[u.fragments.front().address.channel].queue.erase(u.id);u.stage=UnitStage::Cancelled;', 'erase_queued(u);u.stage=UnitStage::Cancelled;')
edit('src/host/host_driver.cpp','channels_[key.block.channel].queue.erase(uid);u.stage=UnitStage::Done;', 'erase_queued(u);u.stage=UnitStage::Done;')
edit('src/host/host_driver.cpp', '    std::set<SendUnitId> tried;', '    std::set<SendUnitId> tried;\n    std::optional<std::pair<std::uint64_t,SendUnitId>> fcfs_cursor;')
edit('src/host/host_driver.cpp', '            tried.insert(chosen);', '            tried.insert(chosen);\n            fcfs_cursor=std::make_pair(u.enqueue_sequence,chosen);')
edit('src/host/host_driver.cpp', '        if(!handoff.attempt)throw', '        fcfs_cursor.reset(); // A successful handoff may unblock read predecessors.\n        if(!handoff.attempt)throw')
old='''        for(auto uid:channel.queue) {
            if(profile_)profile_->add(RuntimeCounter::PumpQueueVisits);
            const auto& u=units_.at(uid);if(tried.count(uid)||!eligible(u))continue;
            const bool open=u.content && channel.open.count({*u.content,u.fragments.front().logical.page});
            candidates.push_back({uid,open,u.replay,u.enqueue_sequence});
        }'''
new='''        if(config_.send_policy=="fcfs") {
            // No cached eligibility: dependencies, retries and open DLUs are live.
            for(auto age_it=fcfs_cursor?channel.age_queue.upper_bound(*fcfs_cursor):channel.age_queue.begin();age_it!=channel.age_queue.end();++age_it) {
                const auto& [sequence,uid]=*age_it;
                if(profile_)profile_->add(RuntimeCounter::PumpQueueVisits);
                const auto& u=units_.at(uid);
                if(sequence!=u.enqueue_sequence||!channel.queue.count(uid))
                    throw std::logic_error("stale FCFS age index");
                if(tried.count(uid)||!eligible(u))continue;
                const bool open=u.content && channel.open.count({*u.content,u.fragments.front().logical.page});
                candidates.push_back({uid,open,u.replay,u.enqueue_sequence});break;
            }
        } else {
''' + old + '''
        }
#ifdef HBF_FCFS_SCAN_ORACLE
        // Independent original selection and complete index membership checks.
        std::set<std::pair<std::uint64_t,SendUnitId>> expected_age;
        std::vector<HostSendCandidate> reference;
        for(auto uid:channel.queue) {
            const auto& u=units_.at(uid);
            if(u.enqueue_sequence)expected_age.insert({u.enqueue_sequence,uid});
            if(tried.count(uid)||!eligible(u))continue;
            const bool open=u.content && channel.open.count({*u.content,u.fragments.front().logical.page});
            reference.push_back({uid,open,u.replay,u.enqueue_sequence});
        }
        if(expected_age!=channel.age_queue)throw std::logic_error("FCFS index membership mismatch");
        if(config_.send_policy=="fcfs" &&
           (reference.empty()!=candidates.empty() ||
            (!reference.empty() && policy_->select(reference)!=policy_->select(candidates))))
            throw std::logic_error("FCFS scan differential mismatch");
#endif'''
edit('src/host/host_driver.cpp',old,new)

# failed_globals_ is monotonic and increments exactly when a parent first fails.
# With no failed parent, scanning read dependencies cannot cancel any unit.
edit('src/host/host_driver.cpp',
 '''        for(auto& item:units_) {
            auto& u=item.second;if(u.op!=Op::Read||u.stage!=UnitStage::Queued)continue;''',
 '''#ifndef HBF_FCFS_SCAN_ORACLE
        if(failed_globals_)
#endif
        for(auto& item:units_) {
            auto& u=item.second;if(u.op!=Op::Read||u.stage!=UnitStage::Queued)continue;''')
