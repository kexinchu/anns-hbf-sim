// Pinned public-port double; online retry and reclamation expectations are local.
#define main pinned_retry_main
#include "../vendor/EventLab/tests/host_retry.cpp"
#undef main
int main(){try{
 HostConfiguration c;c.pending_retry_delay=Tick{10};ScriptFixture f(c);
 f.port.handler=[&](CommandId id,unsigned attempt){
  const auto address=f.port.records.at(id).tx.command.address.local.value;
  if(address==0&&attempt==1)f.port.reply(id,WriteStatus::PendingDluLimit,0,100);
  else f.port.store(id);
 };
 f.host.start_incremental();f.host.submit(write(1,0));
 f.port.events.set_limits({200000,10000,10000});f.port.events.run();
 check(f.host.workload_success(),"online retry succeeds");
 check(f.host.activity().drained(),"online retry drains");
 check(f.host.storage().units==0,"terminal units reclaimed after retry");
 check(f.host.statistics().pending_retry_commands==1,"exactly one refused fragment retried");
 for(unsigned slot=1;slot<64;++slot)check(f.port.attempts[slot*64]==1,"valid fragments not replayed");
 std::cout<<"PASS incremental retry terminal index\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
