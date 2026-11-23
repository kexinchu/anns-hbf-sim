# Applied after the base reset overlay. All edits are single-anchor checked.
edit('include/hbf_eventlab/runtime/device_driver.hpp','    PhysicalNandAddress physical_address', '''    struct ExternalPacket { std::uint64_t epoch; DeliveredResponse delivery; };
    void hold_external_responses(bool hold) { external_hold_=hold; }
    std::vector<ExternalPacket> take_external_packets();
    bool receive_external(const ExternalPacket&);
    std::optional<HandoffResult> try_submit_external(std::uint64_t,std::uint64_t,const LocalTransaction&,Receiver,AcceptanceObserver = {});
    std::size_t external_pending() const { return external_waiters_.size(); }
    std::array<std::uint64_t,4> reset_domains(ChannelId ch) const;
    PhysicalNandAddress physical_address''')
edit('include/hbf_eventlab/runtime/device_driver.hpp','void reset_fault(ChannelId,bool power_loss=false,int die=-1);','void reset_fault(ChannelId,bool power_loss=false,int die=-1,unsigned type=2);')
edit('include/hbf_eventlab/runtime/device_driver.hpp','unsigned type=0;Tick boot{};', 'unsigned type=0;Tick boot{};int fault_die=-1;std::uint64_t link_epoch=0,aou_epoch=0,warm_epoch=0;')
edit('include/hbf_eventlab/runtime/device_driver.hpp','    std::map<ChannelId,ResetControl> reset_controls_;', '''    struct ExternalWaiter { std::uint64_t epoch; ChannelId channel; CommandId command; unsigned die; DeliveredResponse delivery; Receiver receiver; };
    std::map<std::uint64_t,ExternalWaiter> external_waiters_;
    std::map<CommandKey,std::pair<std::uint64_t,std::uint64_t>> request_watermarks_;
    std::vector<ExternalPacket> external_packets_;
    bool external_hold_=false;
    static constexpr std::size_t external_limit_=256;
    void detach_external(DeliveredResponse,Receiver,ChannelAddress,std::uint64_t);
    void reset_external(ChannelId,int,unsigned);
    void flush_external();
    std::map<ChannelId,ResetControl> reset_controls_;''')
edit('include/hbf_eventlab/runtime/device_driver.hpp','        bool released=false,cache_pending=false,reset_invalidated=false;','        bool released=false,cache_pending=false,reset_invalidated=false;\n        std::uint64_t link_epoch=0;')
edit('include/hbf_eventlab/runtime/device_driver.hpp','#include <variant>','#include <variant>\n#include <array>')
edit('src/runtime/device_driver.cpp','    if(identities_.count({ch,cmd.id}))', '''    for(const auto& [_,w]:external_waiters_)if(w.channel==ch&&w.command==cmd.id)
        throw std::logic_error("duplicate external command");
    if(identities_.count({ch,cmd.id}))''')
edit('src/runtime/device_driver.cpp','    if(!channel.rx.fits(payload))', '''    if(external_hold_ && transactions_.size()+external_waiters_.size()+external_packets_.size()>=external_limit_)
        waits.push_back(WaitKey::channel_key(WaitReason::ResultSpace,ch));
    if(!channel.rx.fits(payload))''')
edit('src/runtime/device_driver.cpp','    transactions_.emplace(id.value,std::move(transaction));', '''    transaction.link_epoch=reset_controls_[ch].link_epoch;
    transactions_.emplace(id.value,std::move(transaction));''')
edit('src/runtime/device_driver.cpp','        auto receiver=std::move(tx.receiver);', '''        auto receiver=std::move(tx.receiver);
        const auto address=tx.input.command.address;const auto epoch=tx.link_epoch;''')
edit('src/runtime/device_driver.cpp','        receiver(response); // Host owns delivered symbolic bytes from this boundary.',
 '        detach_external(std::move(response),std::move(receiver),address,epoch);')
edit('src/runtime/device_driver.cpp','    a.unsettled_transfers=transactions_.size();',
 '    a.unsettled_transfers=transactions_.size()+external_waiters_.size()+external_packets_.size();')
p=dst/'src/runtime/device_driver.cpp';p.write_text(p.read_text()+'\n#include "external_reset_control.inc"\n')
(dst/'src/runtime/external_reset_control.inc').write_text((pathlib.Path(__file__).parent/'external_reset_control.inc').read_text())
