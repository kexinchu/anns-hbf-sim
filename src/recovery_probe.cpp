#include "hbf_eventlab/runtime/read_path.hpp"
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include "../vendor/EventLab/examples/support/bounded_read_results.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(){try{
 Geometry g{1,1,1,8,2,1};StaticDeviceDescription d(g,{256,8,true,true},{256,Tick{10000000},g.block_group_dlus()});
 ReferenceAddressLayout layout(g);ZoneMapping zones(d);BlockReplacement replacements(g);NandMediaState media(g);
 CapacityRetirementCoordinator capacity(d,layout,zones,replacements,media);EventQueue events;AdmissionWaitRegistry signals(events);
 CommandAdmission admission(1,256,signals);WritePath writes(d,layout,capacity,media,events,admission);
 test_support::BoundedReadResults results(256);ReadPath reads(d,layout,capacity,media,admission,writes,results);
 std::uint64_t id=0;char action;unsigned page;std::uint64_t value;
 while(std::cin>>action>>page>>value){
  std::string accepted="none";
  if(action=='W'||action=='R'){
   HostCommand c{CommandId{++id},action=='W'?Op::Write:Op::Read,{0,LocalByteAddress{page*4096ull}},action=='W'?4096u:64u,0};
   SubmitResult a;
   if(action=='W')a=writes.submit(c,std::vector<DataToken>(64,DataToken{value})).admission;
   else {auto r=reads.submit(c);a=r.admission;if(r.candidate){auto o=reads.issue(*r.candidate);if(o)reads.finish_read(o->id);}}
   accepted=a==SubmitResult::Accepted?"accepted":"backpressured";
  }else if(action=='E'){
   for(auto e:writes.pending_erases())writes.finish_erase(writes.issue_erase(e.id)->id);
  }else if(action=='P'||action=='F'||action=='U'){
   auto c=writes.program_candidate({0,LocalDlu{page}});if(!c)throw std::runtime_error("no program candidate");
   auto o=writes.issue_program(*c);if(!o)throw std::runtime_error("program blocked");
   writes.finish_program(o->id,action=='P'?ProgramOutcome::Success:action=='F'?ProgramOutcome::FailedReusable:ProgramOutcome::FailedUnusable);
  }else if(action=='D'){
   for(auto r:writes.responses())writes.response_delivered(0,r.command);
   for(auto r:reads.responses())reads.response_delivered(0,r.command);
  }else throw std::invalid_argument("unknown recovery action");
  std::cout<<"{\"acceptance\":\""<<accepted<<"\",\"outstanding\":"<<admission.outstanding(0)<<",\"responses\":[";
  bool first=true;for(auto r:writes.responses()){if(!first)std::cout<<',';first=false;std::cout<<'['<<r.command.value<<",\"W\","<<unsigned(r.status)<<','<<unsigned(r.additional_info)<<",null]";}
  for(auto r:reads.responses()){if(!first)std::cout<<',';first=false;std::cout<<'['<<r.command.value<<",\"R\","<<unsigned(r.status)<<",0,";if(r.data)std::cout<<r.data->value;else std::cout<<"null";std::cout<<']';}std::cout<<"],\"physical_block\":";
  if(capacity.retired({0,0,0,0}))std::cout<<"null";else std::cout<<capacity.inspect({0,LocalByteAddress{0}}).block;
  std::cout<<"}\n";
 }
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
