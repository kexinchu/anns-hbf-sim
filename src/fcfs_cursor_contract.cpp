// Reuse the pinned scripted port; expectations below are independently specified.
#define main pinned_policy_main
#include "../vendor/EventLab/tests/host_send_policy.cpp"
#undef main
int main(){try{
 HostConfiguration c;c.hints=ReadHintMode::AllRegular;ScriptFixture f(c);
 f.port.spacing=0;f.port.gate(0,Tick{10});
 f.port.blocked=[&](const LocalTransaction& tx){return tx.command.address.local.value==128&&f.port.events.now()<Tick{11};};
 f.port.at(Tick{11},[&]{f.port.signals.notify(WaitKey::channel_key(WaitReason::IngressSpace,0));});
 auto predecessor=read(1,0,Tick{10});predecessor.group=7;
 auto older=read(2,64);older.group=7;
 f.run({predecessor,older,read(3,128)});
 check(f.port.addresses()==std::vector<std::uint64_t>{0,64,128},"successful bypass must recheck older newly eligible read");
 check(f.port.records.at(f.port.order[1]).handed==Tick{10},"unblocked predecessor keeps original age");
 std::cout<<"PASS FCFS cursor reset after successful handoff\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
