// Thin adapter only. Expected protocol state lives in Python, never in this process.
#include "hbf_eventlab/runtime/read_path.hpp"
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include "../vendor/EventLab/examples/support/bounded_read_results.hpp"
#include <iostream>
#include <sstream>
using namespace hbf_eventlab;
int main(){try{
 Geometry g{1,1,1,8,2,1}; StaticDeviceDescription d(g,{256,8,true,true},{256,Tick{10000000},g.block_group_dlus()});
 ReferenceAddressLayout layout(g); ZoneMapping zones(d); BlockReplacement replacements(g); NandMediaState media(g);
 CapacityRetirementCoordinator capacity(d,layout,zones,replacements,media); EventQueue events;
 AdmissionWaitRegistry signals(events); CommandAdmission admission(1,256,signals);
 WritePath writes(d,layout,capacity,media,events,admission);
 test_support::BoundedReadResults results(256); ReadPath reads(d,layout,capacity,media,admission,writes,results);
 std::string line; unsigned step=0; std::uint64_t id=0;
 while(std::getline(std::cin,line)){
  std::istringstream input(line); char action; std::uint64_t address=0,value=0; if (!(input>>action>>address>>value) || (input>>std::ws && !input.eof()))
   throw std::invalid_argument("malformed probe record");
  std::string acceptance="none";
  if(action=='W'||action=='R'||action=='Q'){
   HostCommand cmd{CommandId{++id},action=='W'?Op::Write:Op::Read,{0,LocalByteAddress{address}},64,static_cast<std::uint16_t>(id)};
   if(action=='Q'){cmd.axi_id=1;cmd.read_group=1;}
   try{
    SubmitResult a;
    if(action=='W') a=writes.submit(cmd,{DataToken{value}}).admission;
    else {auto r=reads.submit(cmd);a=r.admission;if(r.candidate){auto op=reads.issue(*r.candidate);if(op)reads.finish_read(op->id);}}
    acceptance=a==SubmitResult::Accepted?"accepted":"backpressured";
   }catch(const std::invalid_argument&){acceptance="invalid_api";}
  }else if(action=='T'){
   events.run(); // explicit advance through pending assembly deadlines
  }else if(action=='P'){
   for(const auto& e:writes.pending_erases()){auto issued=writes.issue_erase(e.id);if(issued)writes.finish_erase(issued->id);}
   // Explicit external media completion action; no hidden time progress.
   for(unsigned page=0;page<16;page++){
    auto candidate=writes.program_candidate({0,LocalDlu{page}});
    if(candidate){auto op=writes.issue_program(*candidate);if(op)writes.finish_program(op->id);}
   }
  }else if(action=='D'){
   for(const auto& r:reads.responses())reads.response_delivered(0,r.command);
   for(const auto& r:writes.responses())writes.response_delivered(0,r.command);
   for(std::uint64_t n=1;n<=id;n++){auto candidate=reads.candidate(0,CommandId{n});if(candidate){auto op=reads.issue(*candidate);if(op)reads.finish_read(op->id);}}
  }else throw std::runtime_error("unknown action");
  std::cout<<"{\"step\":"<<step++<<",\"acceptance\":\""<<acceptance<<"\",\"outstanding\":"<<admission.outstanding(0)<<",\"responses\":[";
  bool first=true;
  for(const auto&r:reads.responses()){if(!first)std::cout<<',';first=false;std::cout<<"["<<r.command.value<<",\"R\","<<unsigned(r.status)<<",";if(r.data)std::cout<<r.data->value;else std::cout<<"null";std::cout<<"]";}
  for(const auto&r:writes.responses()){if(!first)std::cout<<',';first=false;std::cout<<"["<<r.command.value<<",\"W\","<<unsigned(r.status)<<",null]";}
  std::cout<<"]}\n";
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
