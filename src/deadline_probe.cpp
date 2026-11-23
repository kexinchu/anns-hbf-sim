#include "hbf_eventlab/runtime/write_path.hpp"
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 if(argc!=3)throw std::invalid_argument("expected offset and nested-arrival flag");
 auto offset=std::stoll(argv[1]);bool nested=std::stoi(argv[2]);
 Geometry g{1,1,1,8,2,1};StaticDeviceDescription d(g,{256,8,true,true},{256,Tick{100},g.block_group_dlus()});
 ReferenceAddressLayout layout(g);ZoneMapping zones(d);BlockReplacement replacements(g);NandMediaState media(g);
 CapacityRetirementCoordinator capacity(d,layout,zones,replacements,media);EventQueue events;
 AdmissionWaitRegistry signals(events);CommandAdmission admission(1,256,signals);WritePath writes(d,layout,capacity,media,events,admission);
 auto send=[&](unsigned slot){HostCommand c{CommandId{slot+1},Op::Write,{0,LocalByteAddress{slot*64}},64,0};writes.submit(c,{DataToken{slot}});};
 for(unsigned i=0;i<63;++i)send(i);
 for(auto e:writes.pending_erases())writes.finish_erase(writes.issue_erase(e.id)->id);
 auto at=Tick{static_cast<std::uint64_t>(100+offset)};
 events.schedule_at(at,EventPhase::Arrival,[&]{if(nested)events.schedule_at(events.now(),EventPhase::Arrival,[&]{send(63);});else send(63);});
 events.run();
 auto candidate=writes.program_candidate({0,LocalDlu{0}});
 if(candidate)writes.finish_program(writes.issue_program(*candidate)->id);
 std::cout<<"[";bool first=true;for(auto r:writes.responses()){if(!first)std::cout<<",";first=false;std::cout<<"["<<r.command.value<<","<<unsigned(r.status)<<"]";}std::cout<<"]\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
