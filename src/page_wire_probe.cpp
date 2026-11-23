#include "eventlab_page_writeback.hpp"
#include <iostream>
#include <sstream>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 bool mutate=argc>1&&std::string(argv[1])=="bad_ack";
 SimulationConfiguration config;config.device.geometry.host_channels=1;config.host.max_resident_fragments=512;
 SimulationSession session(resolve_configuration(config));VersionedPages pages;EventLabPageWriteback bridge(pages);
 bool injected=false;if(argc>1&&std::string(argv[1])=="program_fail")session.set_program_outcome([&](const ProgramOperation&){if(!injected){injected=true;return ProgramOutcome::FailedReusable;}return ProgramOutcome::Success;});
 std::map<std::uint64_t,EventLabPageWriteback::Ack> acks;unsigned completed=0;
 session.set_completion_handler([&](const GlobalCompletion& c){acks.emplace(c.result.id.value,bridge.completion(c));++completed;});
 std::string line;while(std::getline(std::cin,line)){std::istringstream in(line);std::string op,r="invalid";std::uint64_t a=0,b=0,c=0;in>>op>>a>>b>>c;
  if(op=="fill"){r=pages.begin(int(a),int(b));if(r=="accepted")r=pages.publish(int(a),true);}
  else if(op=="dirty")r=pages.dirty(int(a));
  else if(op=="send"){try{bridge.submit(session,a,int(b),a,c);r="sent";}catch(const std::invalid_argument&e){std::cerr<<e.what()<<"\n";r="rejected";}}
  else if(op=="pump"){auto report=session.advance_until_yield();r=report.run.status==RunStatus::WaitingForInput?"drained":"error";}
  else if(op=="ack"){if(acks.count(a)){auto x=acks.at(a);if(mutate&&pages.writebacks.count(x.page)){auto w=pages.writebacks.at(x.page);x.token=w.token;x.epoch=w.epoch;}r=bridge.deliver(x);}}
  else if(op=="oldfail"){if(acks.count(a)){auto x=acks.at(a);x.success=false;r=bridge.deliver(x);}}
  else if(op=="evict")r=pages.evict(int(a));
  else if(op=="refresh")r=pages.refresh(int(a));
  std::cout<<"{\"result\":\""<<r<<"\",\"completed\":"<<completed<<",\"frames\":[";
  for(int i=0;i<2;i++){auto&f=pages.frames[i];std::cout<<(i?",":"")<<"["<<f.page<<","<<f.generation<<",\""<<f.state<<"\","<<f.pins<<","<<f.dirty<<"]";}
  auto st=session.host().statistics();std::cout<<"],\"accepted\":"<<st.accepted<<",\"responses\":"<<st.responses<<",\"errors\":"<<st.attempt_errors<<",\"replay\":"<<st.replay_commands<<"}\n";
 }
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
