namespace hbf_eventlab {
std::optional<HandoffResult> DeviceDriver::try_submit_external(std::uint64_t epoch,std::uint64_t generation,const LocalTransaction& request,Receiver receiver,AcceptanceObserver acceptance) {
    const auto ch=request.command.address.channel;
    if(ch>=channels_.size())throw std::invalid_argument("external request channel");
    // Before duplicate-ID lookup, RX reservation or any media/path side effect.
    if(epoch!=reset_controls_[ch].link_epoch)return std::nullopt;
    if(!generation || request.command.id.value>=16384 || request.command.axi_id>=16384)
        throw std::invalid_argument("external request identity range");
    const CommandKey key{ch,request.command.id};auto it=request_watermarks_.find(key);
    if(it!=request_watermarks_.end()&&it->second.first==epoch&&generation<=it->second.second)return std::nullopt;
    auto result=try_submit(request,std::move(receiver),std::move(acceptance));
    if(result.disposition==HandoffDisposition::Taken)request_watermarks_[key]={epoch,generation};
    return result;
}
std::array<std::uint64_t,4> DeviceDriver::reset_domains(ChannelId ch) const {
    if(ch>=channels_.size())throw std::invalid_argument("reset channel");
    auto it=reset_controls_.find(ch);const ResetControl c=it==reset_controls_.end()?ResetControl{}:it->second;
    return {c.link_epoch,c.link_epoch,c.aou_epoch,c.warm_epoch};
}
std::vector<DeviceDriver::ExternalPacket> DeviceDriver::take_external_packets() {
    auto out=std::move(external_packets_);external_packets_.clear();
    for(ChannelId c=0;c<channels_.size();++c)signals_.notify(WaitKey::channel_key(WaitReason::ResultSpace,c));
    return out;
}
void DeviceDriver::detach_external(DeliveredResponse response,Receiver receiver,ChannelAddress address,std::uint64_t epoch) {
    if(response.reset_invalidated){receiver(response);return;}
    const auto command=std::visit([](const auto& r){return r.command;},response.response);
    const auto id=response.attempt.value;
    unsigned die=std::numeric_limits<unsigned>::max();
    try {die=capacity_.inspect(address).die;}catch(const std::out_of_range&){}
    ExternalWaiter waiter{epoch,address.channel,command,die,response,std::move(receiver)};
    external_waiters_.emplace(id,std::move(waiter));
    ExternalPacket packet{epoch,std::move(response)};
    if(external_hold_ || !receive_external(packet))external_packets_.push_back(std::move(packet));
}
bool DeviceDriver::receive_external(const ExternalPacket& packet) {
    const auto id=packet.delivery.attempt.value;auto it=external_waiters_.find(id);
    if(it==external_waiters_.end())return false;
    const auto& w=it->second;
    const auto ch=std::visit([](const auto& r){return r.channel;},packet.delivery.response);
    const auto command=std::visit([](const auto& r){return r.command;},packet.delivery.response);
    const auto& control=reset_controls_[w.channel];
    const bool blocked=reset_blocked(w.channel)&&(control.fault_die<0||w.die==unsigned(control.fault_die));
    if(blocked || packet.epoch!=w.epoch || packet.epoch!=reset_controls_[w.channel].link_epoch ||
       ch!=w.channel || command!=w.command || packet.delivery.response.index()!=w.delivery.response.index() ||
       packet.delivery.reset_invalidated)return false;
    auto receiver=std::move(it->second.receiver);external_waiters_.erase(it);
    // Never release a current queue entry based solely on an AXI/command ID.
    for(ChannelId c=0;c<channels_.size();++c)signals_.notify(WaitKey::channel_key(WaitReason::ResultSpace,c));
    receiver(packet.delivery);return true;
}
void DeviceDriver::flush_external() {
    if(external_hold_)return;
    auto packets=take_external_packets();
    for(const auto& p:packets)if(!receive_external(p)&&external_waiters_.count(p.delivery.attempt.value))external_packets_.push_back(p);
}
void DeviceDriver::reset_external(ChannelId ch,int die,unsigned type) {
    // Only bounded unacknowledged records are retained, never a lifetime history.
    std::set<std::uint64_t> affected;
    std::vector<ExternalWaiter> cancelled;
    std::vector<ExternalPacket> replay;
    for(auto it=external_waiters_.begin();it!=external_waiters_.end();){auto& w=it->second;
        if(w.channel!=ch||(die>=0&&w.die!=unsigned(die))){++it;continue;}
        affected.insert(it->first);
        if(type==0 && die<0){
            // Model choice: PHY/D2D reset retains completed AoU response records.
            // Reissue with a new link epoch, never bless the old packet itself.
            w.epoch=reset_controls_[ch].link_epoch;replay.push_back({w.epoch,w.delivery});++it;
        } else {cancelled.push_back(std::move(w));it=external_waiters_.erase(it);}
    }
    // Old externally captured values remain injectable. Undelivered local copies
    // are discarded here to keep reset/replay storage bounded.
    external_packets_.erase(std::remove_if(external_packets_.begin(),external_packets_.end(),[&](const auto& p){
        return affected.count(p.delivery.attempt.value)!=0;
    }),external_packets_.end());
    for(auto& packet:replay)external_packets_.push_back(std::move(packet));
    for(auto& w:cancelled){auto response=w.delivery;response.reset_invalidated=true;
        if(auto* r=std::get_if<ReadResponse>(&response.response))r->data.reset();
        schedule(events_.now(),EventPhase::Arrival,[receiver=std::move(w.receiver),response]{receiver(response);});
    }
    for(ChannelId c=0;c<channels_.size();++c)signals_.notify(WaitKey::channel_key(WaitReason::ResultSpace,c));
}
}
