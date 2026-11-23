// Functional reset overlay. Cleanup callbacks drain in virtual time; they do not
// represent powered hardware continuing to execute after a power cut.
namespace hbf_eventlab {
bool DeviceDriver::reset_blocked(ChannelId ch) const {
    auto it=reset_controls_.find(ch);
    return it!=reset_controls_.end()&&(!it->second.power||!it->second.ready||!it->second.enabled);
}
bool DeviceDriver::reset_block_fenced(PhysicalBlockKey block) const {
    for(const auto& [id,t]:transactions_)if(t.reset_invalidated&&t.input.command.op==Op::Write) {
        try {if(block_of(capacity_.inspect(t.input.command.address))==block)return true;}
        catch(const std::out_of_range&) {}
    }
    return false;
}
std::uint32_t DeviceDriver::reset_csr_read(ChannelId ch,unsigned offset) const {
    if(ch>=channels_.size())throw std::invalid_argument("reset channel");
    auto it=reset_controls_.find(ch);const ResetControl c=it==reset_controls_.end()?ResetControl{}:it->second;
    if(!c.power)throw std::invalid_argument("CSR power off");
    if(offset==0x0c)return c.enabled;
    if(offset==0x10)return c.ready;
    if(offset==0x14)return c.type;
    throw std::invalid_argument("unsupported reset CSR");
}
void DeviceDriver::reset_fault(ChannelId ch,bool power_loss,int die) {
    if(ch>=channels_.size()||die < -1||die>=int(description_.geometry().dies_per_channel))throw std::invalid_argument("reset target");
    auto& control=reset_controls_[ch];control.ready=false;control.enabled=false;
    if(power_loss)control.power=false;
    control.boot=Tick{checked_add(events_.now().value,1000)}; // uncalibrated functional delay
    for(auto id:channels_[ch]->transactions){auto& t=transactions_.at(id);const auto& cmd=t.input.command;
        std::optional<PhysicalNandAddress> physical;
        try {physical=capacity_.inspect(cmd.address);}catch(const std::out_of_range&) {}
        if(die>=0&&(!physical||physical->die!=unsigned(die)))continue;
        t.reset_invalidated=true;
        // Completed media is retained even if its ACK has not crossed Feedback.
        if(cmd.op==Op::Write&&physical&&t.stage!=Stage::Egress&&t.stage!=Stage::ResponseLink&&t.stage!=Stage::Feedback&&!writes_.response(ch,cmd.id))
            reset_unknown_.insert(block_of(*physical));
    }
    cache_.invalidate_all();
}
void DeviceDriver::reset_csr_write(ChannelId ch,unsigned offset,std::uint32_t value) {
    if(ch>=channels_.size())throw std::invalid_argument("reset channel");
    auto& c=reset_controls_[ch];if(!c.power)throw std::invalid_argument("CSR power off");
    if(offset==0x0c){if(value>1)throw std::invalid_argument("unsupported EN field");c.enabled=value;if(value)signals_.notify(WaitKey::channel_key(WaitReason::RequestLink,ch));return;}
    if(offset!=0x14)throw std::invalid_argument("read-only CSR");
    if(value>>8!=0x484246)return;
    if((value&0xfc)||(value&3)==3)throw std::invalid_argument("reserved reset type");
    reset_fault(ch);c.type=value&3;
}
bool DeviceDriver::reset_recover(ChannelId ch) {
    if(ch>=channels_.size())throw std::invalid_argument("reset channel");
    auto& c=reset_controls_[ch];
    // Conservative device-wide quiescence: includes assembly deadlines, waiter
    // callbacks, cache leases, bank tickets, RX/TX reservations and feedback.
    if(!activity().drained()||events_.now()<c.boot)return false;
    writes_.reset_drained_channel(ch,reset_unknown_);
    c.power=true;c.ready=true;
    signals_.notify(WaitKey::channel_key(WaitReason::RequestLink,ch));return true;
}
}
