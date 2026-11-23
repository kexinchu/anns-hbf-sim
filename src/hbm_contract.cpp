#include "physical/hbm/hbm_device.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace hbfsim::physical;
using namespace hbfsim::physical::hbm;
void require(bool v,const char*s){if(!v)throw std::runtime_error(s);}
template<class F>void rejects(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}require(caught,"missing rejection");}
PhysicalRequest req(std::uint64_t addr,std::uint64_t bytes,double t=0){return {.id="test",.tier=Tier::HBM,.op=Op::Read,.arrival_ns=t,.addr=addr,.bytes=bytes};}
int main(){try{
 HbmConfig c;c.replicate_symmetric_pseudo_channels=false;
 HbmDevice d(c);
 for(std::uint64_t a=0;a<65536;a+=13)require(d.encode(d.decode(a))==a,"mapping roundtrip");
 auto one=d.issue(req(0,c.burst_bytes()));
 // Independent single-cold-burst formula: ACT -> tRCD -> RD -> CL -> data burst.
 auto tick=double(c.data_rate_per_command_clock)/c.pin_rate_Gbps;
 auto rounded=[&](double n){return std::ceil(n/tick)*tick;};
 auto expected=rounded(c.tRCDRD_ns)+rounded(c.tCL_ns)+rounded(c.burst_duration_ns());
 require(std::abs(one.finish_ns-expected)<1e-8,"cold read analytical mismatch");
 require(one.physical_bytes==c.burst_bytes(),"cold burst bytes");
 HbmDevice cross(c);auto x=cross.issue(req(c.burst_bytes()-1,2));
 require(x.logical_bytes==2&&x.physical_bytes==2*c.burst_bytes(),"cross-burst accounting");
 HbmDevice capacity(c);rejects([&]{(void)capacity.issue(req(c.capacity_bytes-1,2));});
 HbmDevice order(c);(void)order.issue(req(0,32,100));rejects([&]{(void)order.issue(req(64,32,99));});
 HbmDevice queued(c);auto a=queued.enqueue(req(0,32));auto b=queued.enqueue(req(32,32));
 auto ca=queued.pump(a),cb=queued.pump(b);require(cb.finish_ns>ca.finish_ns,"same-lane contention missing");
 require(queued.stats().read_bytes==64,"queue bytes");
 std::cout<<"{\"status\":\"PASS\",\"scope\":\"HBM_SOFTWARE_CONTRACT_ONLY\",\"checks\":[\"mapping_roundtrip\",\"cold_burst_analytic\",\"cross_burst_bytes\",\"capacity_rejection\",\"arrival_order_rejection\",\"same_lane_contention\"],\"cold_ns\":"<<one.finish_ns<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
