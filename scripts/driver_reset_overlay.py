# Invoked with prepare_eventlab.py's checked single-anchor edit function.
edit('include/hbf_eventlab/interfaces/host_port.hpp',
 'struct DeliveredResponse { TransferAttemptId attempt; DeviceResponse response; Tick at; };',
 '''// Simulator transport interruption metadata, NOT a new OCP status/packet field.
struct DeliveredResponse { TransferAttemptId attempt; DeviceResponse response; Tick at; bool reset_invalidated=false; };''')
edit('include/hbf_eventlab/runtime/device_driver.hpp','    void declare_discardable(ChannelId,std::uint64_t);',
 '''    PhysicalNandAddress physical_address(ChannelAddress a) const { return capacity_.inspect(a); }
    std::uint32_t reset_csr_read(ChannelId,unsigned) const;
    void reset_csr_write(ChannelId,unsigned,std::uint32_t);
    void reset_fault(ChannelId,bool power_loss=false,int die=-1);
    bool reset_recover(ChannelId);
    bool uncertain(ChannelAddress a) const { return reset_unknown_.count(block_of(capacity_.inspect(a))); }
    void declare_discardable(ChannelId,std::uint64_t);''')
edit('include/hbf_eventlab/runtime/device_driver.hpp','        bool released=false,cache_pending=false;',
 '        bool released=false,cache_pending=false,reset_invalidated=false;')
edit('include/hbf_eventlab/runtime/device_driver.hpp','    enum class Stage {',
 '''    struct ResetControl {bool power=true,ready=true,enabled=true;unsigned type=0;Tick boot{};};
    std::map<ChannelId,ResetControl> reset_controls_;
    std::set<PhysicalBlockKey> reset_unknown_;
    bool reset_blocked(ChannelId ch) const;
    bool reset_block_fenced(PhysicalBlockKey) const;
    enum class Stage {''')
edit('include/hbf_eventlab/runtime/write_path.hpp','    void finish_erase(OperationId);','    void finish_erase(OperationId,bool commit_media=true);')
edit('src/runtime/write_path.cpp','void WritePath::finish_erase(OperationId id) {','void WritePath::finish_erase(OperationId id,bool commit_media) {')
edit('src/runtime/write_path.cpp','    media_.erase(op.physical);','    if(commit_media)media_.erase(op.physical);')
edit('src/runtime/device_driver.cpp','    if(channel.request_busy)return {link};','    if(channel.request_busy || reset_blocked(ch))return {link};')
edit('src/runtime/device_driver.cpp','    if(channel.request_busy) waits.push_back(', '    if(channel.request_busy || reset_blocked(ch)) waits.push_back(')
edit('src/runtime/device_driver.cpp','    ++stats_.ingress_attempts;','''    if(cmd.op==Op::Read) {
        try { if(uncertain(cmd.address))t.reset_invalidated=true; } catch(const std::out_of_range&) {}
    }
    ++stats_.ingress_attempts;''')
edit('src/runtime/device_driver.cpp','                cache_.invalidate(op.physical); writes_.finish_erase(op.id);',
 '''                const bool fenced=reset_block_fenced(op.physical);
                cache_.invalidate(op.physical); writes_.finish_erase(op.id,!fenced);
                if(!fenced)reset_unknown_.erase(op.physical);''')
edit('src/runtime/device_driver.cpp','                const auto outcome=outcome_(op);',
 '''                const auto outcome=reset_block_fenced(block_of(op.physical))?
                    ProgramOutcome::FailedReusable:outcome_(op);''')
edit('src/runtime/device_driver.cpp','        DeliveredResponse response{tx.id,std::move(*tx.delivered),delivery_time};',
 '''        DeliveredResponse response{tx.id,std::move(*tx.delivered),delivery_time,tx.reset_invalidated};
        if(response.reset_invalidated)if(auto* read=std::get_if<ReadResponse>(&response.response))read->data.reset();''')
edit('src/host/host_driver.cpp','    bool success=false;\n    if(u.op==Op::Write) {',
 '''    bool success=false;
    if(response.reset_invalidated) {
        // Preserve all normal attempt/DLU cleanup below, but never replay a stale
        // success/failure as a fresh device completion or publish its payload.
        if(u.op==Op::Write){write_error_seen_=true;abort_version(*u.content,"DeviceResetOrUnknown");}
        for(const auto& f:u.fragments)finish_work(f.id,false,"DeviceResetOrUnknown");
    } else if(u.op==Op::Write) {''')
# Add the implementation beside the donor source without changing the pin.
(dst/'src/runtime/device_reset_control.inc').write_text((pathlib.Path(__file__).parent/'device_reset_control.inc').read_text())
p=dst/'src/runtime/device_driver.cpp';p.write_text(p.read_text()+'\n#include "device_reset_control.inc"\n')
edit('include/hbf_eventlab/host/host_driver.hpp','    void start();', '''    void start();
    // Explicit producer acknowledgement: old results remain Failed. Only permits
    // a new content identity after quiescence; does not repair media or dependencies.
    void acknowledge_reset_loss() {
        if(!activity().drained())throw std::logic_error("reset loss before Host drain");
        for(const auto& [key,v]:versions_)if(v.aborted&&v.reason=="DeviceResetOrUnknown")reset_reconciled_.insert(key);
    }''')
edit('include/hbf_eventlab/host/host_driver.hpp','    std::map<ContentKey,Version> versions_;','    std::map<ContentKey,Version> versions_;\n    std::set<ContentKey> reset_reconciled_;')
edit('src/host/host_driver.cpp','            if(!version_done(older)||versions_.at(older).aborted)return false;',
 '            if(!reset_reconciled_.count(older)&&(!version_done(older)||versions_.at(older).aborted))return false;')
edit('src/host/host_driver.cpp','                if(versions_.at(older).aborted) {abort_version(item.first,"PriorContentFailed");changed=true;break;}',
 '                if(versions_.at(older).aborted&&!reset_reconciled_.count(older)) {abort_version(item.first,"PriorContentFailed");changed=true;break;}')
edit('include/hbf_eventlab/runtime/write_path.hpp','    std::size_t parent_count() const { return parents_.size(); }',
 '''    std::size_t parent_count() const { return parents_.size(); }
    void reset_drained_channel(ChannelId ch,const std::set<PhysicalBlockKey>& unknown) {
        for(auto& [key,b]:blocks_)if(key.channel==ch&&b.physical&&unknown.count(*b.physical)) {
            if(b.outstanding||b.order.has_active_pages()||b.preparation==BlockPreparation::ErasePending)
                throw std::logic_error("reset WritePath before drain");
            b.preparation=BlockPreparation::None;
        }
    }''')
