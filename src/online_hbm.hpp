#pragma once
#include "physical/hbm/hbm_device.hpp"
#include <deque>
#include <map>
#include <memory>
#include <functional>
#include <cmath>
// Online, bounded, nonpreemptive burst FCFS per pseudo-channel.
// One outstanding burst/PC: permits PC concurrency but does NOT claim full FR-FCFS/MLP.
class OnlineHbm {
 using U=std::uint64_t;
 using Done=std::function<void(U,U)>;
 struct Parent {U arrival,remaining;Done done;};
 struct Burst {U address,bytes;bool write;std::shared_ptr<Parent> parent;};
 struct Lane {bool busy=false;std::deque<Burst> queue;};
 hbfsim::physical::hbm::HbmDevice device;
 std::map<U,Lane> lanes;
 U used=0,limit,serial=0,last=0;
 std::function<void(U,std::function<void()>)> schedule;
 std::function<void(U,U,U,U)> observe;
 U lane(U address) const {auto a=device.decode(address);auto&c=device.config();return (a.stack*c.channels_per_stack+a.channel)*c.pseudo_channels_per_channel+a.pseudo_channel;}
 void start(U key,U now){
  auto&l=lanes[key];if(l.busy||l.queue.empty())return;
  auto b=l.queue.front();l.queue.pop_front();l.busy=true;
  using namespace hbfsim::physical;
  auto receipt=device.issue(PhysicalRequest{.id=std::to_string(++serial),.tier=Tier::HBM,.op=b.write?Op::Write:Op::Read,.arrival_ns=double(now)/1000.,.addr=b.address,.bytes=b.bytes});
  U end=U(std::ceil(receipt.finish_ns*1000.));
  if(end<now)throw std::runtime_error("HBM time reversal");
  observe(key,now,end,receipt.physical_bytes);
  schedule(end,[this,key,b,end]{
   lanes[key].busy=false;--used;last=std::max(last,end);
   if(--b.parent->remaining==0)b.parent->done(b.parent->arrival,end);
   // Start only at actual completion, never reserve unknown future arrivals.
   start(key,end);
  });
 }
public:
 OnlineHbm(hbfsim::physical::hbm::HbmConfig c,U capacity,
   std::function<void(U,std::function<void()>)> s,
   std::function<void(U,U,U,U)> o):device(c),limit(capacity),schedule(std::move(s)),observe(std::move(o)){}
 bool submit(U now,bool write,U address,U bytes,Done done){
  if(now<last||bytes==0||address>=device.config().capacity_bytes||bytes>device.config().capacity_bytes-address)
   throw std::invalid_argument("invalid online HBM request");
  U burst=device.config().burst_bytes(),count=(bytes-1)/burst+1+(address%burst+(bytes-1)%burst>=burst);
  if(count>limit-used)return false; // atomic admission; no partial side effects
  last=now;auto parent=std::make_shared<Parent>(Parent{now,count,std::move(done)});
  std::vector<U> keys;
  for(U pos=address,left=bytes;left;){U n=std::min(left,burst-pos%burst),key=lane(pos);
   lanes[key].queue.push_back({pos,n,write,parent});keys.push_back(key);pos+=n;left-=n;++used;}
  for(auto key:keys)start(key,now);
  return true;
 }
 U resident_bursts()const{return used;}
};
