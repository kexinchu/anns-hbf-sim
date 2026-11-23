#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#ifdef ANNS_CUDA
#include "../gpu/race_backend.h"
#else
namespace {int values[4];bool held[4]{};}
void race_init(){} void race_fill(int f,int v){values[f]=v;}void race_start(int f,bool h){held[f]=h;}
bool race_ready(int f){return !held[f];}void race_open(int f){held[f]=false;}
void race_result(int f,long long* a){for(int k=0;k<32;k++){a[k]=0;for(int j=0;j<32;j++){long long d=values[f]+(k*32+j)%17-3;a[k]+=d*d;}}}
void race_copy(int f,int* a){for(int i=0;i<1024;i++)a[i]=values[f]+i%17;}void race_close(){}
#endif
using namespace hbf_eventlab;
void need(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
template<class F> void reject(F f){bool yes=false;try{f();}catch(const std::invalid_argument&){yes=true;}need(yes,"negative escaped");}


#include "aou_link.hpp"
#include "ucie_lifetime.hpp"
int main(int argc,char**argv){bool gpu=false;try{
 unsigned type=argc>1?std::stoul(argv[1]):2,stage=argc>2?std::stoul(argv[2]):0;
 need(type<3&&stage<3,"fixture parameters");
 Geometry g{2,2,1,4,4,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{10000000},g.block_group_dlus()});EventQueue events;ExecutionConfiguration cfg;cfg.core_bytes_per_ns=16;
 DeviceDriver d(desc,cfg,events);RoundRobinInterleaver mapping(GlobalByteAddress{0},2,g.channel_bytes(),64);HostDriver host(d,events,mapping);host.start_incremental();
 host.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},4096,7},GlobalRequest{GlobalRequestId{2},Op::Write,GlobalByteAddress{4096},4096,7}});events.run();
 ucie::Pair transport;aou::Link link;
 auto boot=[&]{for(unsigned e=0;e<2;e++){need(transport.request(e,true),"rx request");need(!transport.acknowledge(e),"zero cycle rx ack");}transport.tick();for(unsigned e=0;e<2;e++){need(transport.acknowledge(e),"rx ack");need(transport.transition(e,ucie::Endpoint::Active),"FDI active");}
 link.activate_request(true);link.activate_request(false);link.activate_ack(true);link.activate_ack(false);link.grant(8);};boot();
 unsigned completions=0,command=1000;std::uint64_t value=0;
 auto consume=[&](const aou::Message&m){++completions;value=0;for(unsigned i=0;i<8;i++)value=(value<<8)|m.data[i];};
 auto ack_wire=[&](unsigned sender){need(transport.queue_ack(sender),"ACK TX");need(transport.launch(sender),"ACK flight");need(transport.arrive(sender),"ACK arrival");};
 auto execute=[&](bool corrupt){need(!link.tx.empty(),"missing request");auto bytes=link.tx.front();link.tx.pop_front();need(transport.send(0,bytes),"request TX");need(transport.launch(0),"request flight");need(transport.arrive(0,corrupt),"request RX");
 if(corrupt){need(transport.ep[1].rx.empty(),"corrupt request escaped");need(transport.replay(0),"request replay");need(transport.launch(0),"request replay flight");need(transport.arrive(0),"request replay RX");}
 aou::Bytes request;need(transport.consume(1,request),"request FDI");auto m=aou::decode(request);ack_wire(1);
 auto h=d.try_submit({HostCommand{CommandId{++command},Op::Read,{0,LocalByteAddress{m.address}},64,std::uint16_t(m.id)},{}},[&,id=m.id](const DeliveredResponse&r){if(r.reset_invalidated)return;auto data=std::get<ReadResponse>(r.response).data;need(data.has_value(),"missing data");aou::Message out;out.kind=4;out.id=id;out.sync=0;for(unsigned i=0;i<8;i++)out.data[i]=data->value>>(56-8*i);need(transport.send(1,aou::encode(out)),"response TX");});need(h.disposition==HandoffDisposition::Taken,"driver handoff");events.run();};
 aou::Message req;req.kind=2;req.id=42;need(link.send(req,consume),"old request");execute(false);
 // Retain actual old response at TX/retry, channel flight, or adapter RX.
 if(stage>=1)need(transport.launch(1),"old launch");if(stage==2)need(transport.arrive(1),"old adapter RX");
 need(!transport.reset_exit(),"reset without transitions");
 for(unsigned e=0;e<2;e++){need(transport.request(e,false),"rx request down");need(!transport.transition(e,ucie::Endpoint::LinkReset),"transition before RX ack down");need(transport.acknowledge(e),"rx ack down");need(transport.transition(e,ucie::Endpoint::LinkReset),"reset entry");}
 link.fail();d.reset_csr_write(0,0x14,0x48424600|type);
 need(!transport.reset_exit(),"reset with owned data");
 // Every old in-flight item traverses the CLOSED receiver, not flight.clear().
 while(transport.arrive(0)){}while(transport.arrive(1)){}
 for(unsigned e=0;e<2;e++)while(transport.cleanup(e)){}
 need(transport.reset_exit(),"reset cleanup incomplete");link.teardown();link.release_ids();
 events.run();events.advance_idle_to(Tick{events.now().value+1001});need(d.reset_recover(0),"device recovery");d.reset_csr_write(0,0x0c,1);boot();
 req.address=64;need(link.send(req,consume),"same ID reuse");execute(true);
 // Lost response ACK: retry remains owned after first delivery. Its duplicate
 // is suppressed at adapter sequence checking, before AoU and CUDA see bytes.
 need(transport.launch(1),"new response flight");need(transport.arrive(1),"new response RX");aou::Bytes fresh;need(transport.consume(0,fresh),"new response FDI");need(link.receive(fresh),"new response callback");
 need(transport.replay(1),"lost ACK replay");need(transport.launch(1),"duplicate flight");need(transport.arrive(1),"duplicate arrival");aou::Bytes duplicate;need(!transport.consume(0,duplicate),"duplicate reached AoU");ack_wire(0);
 need(completions==1,"stale completion");race_init();gpu=true;race_fill(0,int(value%97)+20);race_start(0,false);long long score[32];race_result(0,score);
 if(argc>3&&std::string(argv[3])=="bad_score")++score[0];
 std::cout<<"{\"type\":"<<type<<",\"stage\":"<<stage<<",\"callbacks\":"<<completions<<",\"discarded\":"<<transport.discarded<<",\"flight_drops\":"<<transport.dropped<<",\"crc_errors\":"<<transport.crc_errors<<",\"duplicates\":"<<transport.duplicates<<",\"performance_ready\":false,\"wire_conformance\":false,\"drained\":"<<(d.activity().drained()?"true":"false")<<",\"scores\":[";for(int i=0;i<32;i++)std::cout<<(i?",":"")<<score[i];std::cout<<"]}\n";race_close();gpu=false;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(gpu)race_close();return 1;}}
