"""Ordered stage directories: change host execution work, never simulated scheduling."""
edit('include/hbf_eventlab/runtime/device_driver.hpp','#include <variant>','#include <variant>\n#include <array>')
edit('include/hbf_eventlab/runtime/device_driver.hpp','        std::set<std::uint64_t> transactions;', '        std::array<std::map<std::uint64_t,Transaction*>,6> stages;\n        std::set<std::uint64_t> transactions;')
edit('include/hbf_eventlab/runtime/device_driver.hpp','    void pump(ChannelId);', '''    void set_stage(Transaction& t,Stage next) {
        auto& c=*channels_[t.input.command.address.channel];
        auto& old=c.stages[static_cast<unsigned>(t.stage)];
        if(old.erase(t.id.value)!=1)throw std::logic_error("missing device stage entry");
        t.stage=next;
        if(!c.stages[static_cast<unsigned>(next)].emplace(t.id.value,&t).second)
            throw std::logic_error("duplicate device stage entry");
    }
    const std::map<std::uint64_t,Transaction*>& stage_transactions(ChannelId,Stage) const;
    void pump(ChannelId);''')
edit('src/runtime/device_driver.cpp','    channel.transactions.insert(id.value);', '    channel.transactions.insert(id.value);\n    channel.stages[static_cast<unsigned>(Stage::Link)].emplace(id.value,&transactions_.at(id.value));')
for stage in ['Ingress','Accepted','Egress','ResponseLink','Feedback']:
 edit('src/runtime/device_driver.cpp','t.stage=Stage::'+stage+';', 'set_stage(t,Stage::'+stage+');')
edit('src/runtime/device_driver.cpp','        transactions_.erase(id);', '''        if(channels_[ch]->stages[static_cast<unsigned>(Stage::Feedback)].erase(id)!=1)
            throw std::logic_error("missing feedback stage entry");
        transactions_.erase(id);''')
# Advance before mutation of the current element; retain ascending attempt-ID order.
for signature,stage in [('void DeviceDriver::pump(ChannelId ch) {','Ingress'),('void DeviceDriver::queue_responses(ChannelId ch) {','Accepted'),('void DeviceDriver::start_response(ChannelId ch) {','Egress')]:
 path=dst/'src/runtime/device_driver.cpp';s=path.read_text();begin=s.index(signature);end=s.index('\n}',begin)
 block=s[begin:end];old='for(const auto identity:channels_[ch]->transactions) {\n        '
 assert block.count(old)>=1
 marker=block.index(old);tail=block[marker:]
 # First stage-filtered loop in each function, including pointer lookup.
 import re
 pattern=re.escape(old)+r'(const auto&|auto&) t=transactions_\.at\(identity\);'
 replacement='for(auto it=stage_transactions(ch,Stage::'+stage+').begin(), end=stage_transactions(ch,Stage::'+stage+').end();it!=end;) {\n        auto& t=*it++->second;'
 revised,n=re.subn(pattern,replacement,tail,count=1);assert n==1
 block=block[:marker]+revised;s=s[:begin]+block+s[end:];path.write_text(s)
# Accepted read candidates retain live eligibility/probe checks, including sleepers
# that may have become terminal. Only the already-tested stage predicate is indexed.
path=dst/'src/runtime/device_driver.cpp';s=path.read_text()
old='for(const auto identity:channels_[ch]->transactions) {\n        auto& t=transactions_.at(identity);'
assert s.count(old)==1
s=s.replace(old,'for(auto it=stage_transactions(ch,Stage::Accepted).begin(), end=stage_transactions(ch,Stage::Accepted).end();it!=end;) {\n        auto& t=*it++->second;')
old='for(const auto identity:channels_[ch]->transactions) {\n            auto& t=transactions_.at(identity);'
assert s.count(old)==1
s=s.replace(old,'for(auto it=stage_transactions(ch,Stage::Accepted).begin(), end=stage_transactions(ch,Stage::Accepted).end();it!=end;) {\n            auto& t=*it++->second;')
path.write_text(s)
edit('src/runtime/device_driver.cpp','DeviceActivity DeviceDriver::activity() const {', '''DeviceActivity DeviceDriver::activity() const {
#ifdef HBF_DEVICE_INDEX_ORACLE
    for(ChannelId ch=0;ch<channels_.size();++ch)
        for(unsigned stage=0;stage<6;++stage)(void)stage_transactions(ch,static_cast<Stage>(stage));
#endif''')
# The original predicate is retained verbatim as a CHECK oracle. Probe is const;
# a Ready probe already supplies the same physical address that inspect returns.
path=dst/'src/runtime/device_driver.cpp';s=path.read_text()
begin=s.index('bool DeviceDriver::prior_sense(');end=s.index('\nvoid DeviceDriver::execute_media',begin)
original=s[begin:end];body=original[original.index('{')+1:original.rfind('}')]
optimized=body.replace('for(auto identity:channels_[bank.channel]->transactions) {\n        const auto& older=transactions_.at(identity);','for(const auto& [identity,pointer]:stage_transactions(bank.channel,Stage::Accepted)) {\n        const auto& older=*pointer;').replace('bank_of(capacity_.inspect(older.input.command.address))','bank_of(p.target?*p.target:capacity_.inspect(older.input.command.address))')
assert optimized!=body
replacement=original[:original.index('{')+1]+'\n    auto indexed=[&]() -> bool {'+optimized+'\n    };\n    const bool result=indexed();\n#ifdef HBF_DEVICE_INDEX_ORACLE\n    auto scan=[&]() -> bool {'+body+'\n    };\n    if(result!=scan())throw std::logic_error("prior-sense differential mismatch");\n#endif\n    return result;\n}\n'
path.write_text(s[:begin]+replacement+s[end:])

# Keep CHECK-only implementation out of the header: PUBLIC users need no macro.
edit('src/runtime/device_driver.cpp','namespace hbf_eventlab {',
 'namespace hbf_eventlab {\nconst std::map<std::uint64_t,DeviceDriver::Transaction*>& DeviceDriver::stage_transactions(ChannelId ch,Stage stage) const {\n        const auto& indexed=channels_[ch]->stages[static_cast<unsigned>(stage)];\n#ifdef HBF_DEVICE_INDEX_ORACLE\n        std::map<std::uint64_t,const Transaction*> expected;\n        for(auto id:channels_[ch]->transactions) {\n            const auto& t=transactions_.at(id);\n            if(t.stage==stage)expected.emplace(id,&t);\n        }\n        if(expected.size()!=indexed.size())throw std::logic_error("device stage scan mismatch");\n        for(const auto& [id,p]:indexed) {\n            auto it=expected.find(id);\n            if(it==expected.end()||it->second!=p)throw std::logic_error("device stage identity mismatch");\n        }\n#endif\n        return indexed;\n    }\n')
