#pragma once
#include "bank_hbm.hpp"
#include "physical/hbm/hbm_device.hpp"
#include <functional>
#include <map>
#include <memory>
// Functional single-PC adapter: 64B interleaving over four banks, 1KiB rows.
// Mapping and 1ns cycle are synthetic, not a GPU physical address decoder.
class BankAdapter {
 using U=std::uint64_t;using Done=std::function<void(U,U)>;
 struct Parent {U arrival,left;Done done;};
 struct Child {U id,address;bool write;std::shared_ptr<Parent> parent;};
 BankHbm controller{4,1024};std::deque<Child> waiting;std::map<U,Child> active;
 U address_capacity,limit,used=0,id=0,cycle=0,last=0,next_ps=0;bool running=false;
 std::function<void(U,std::function<void()>)> schedule;
 std::function<void(U,U,U,U)> observe;
 void tick(U now){
  last=now;
  while(!waiting.empty()){auto c=waiting.front();U burst=c.address/64;
   if(!controller.submit(cycle,c.id,burst%4,burst/(4*16),c.write))break;
   active.emplace(c.id,c);waiting.pop_front();
  }
  next_ps=now+1000;
  auto events=controller.step(cycle++);
  for(auto&e:events){auto c=active.at(e.id);
   if(e.op=="RD"||e.op=="WR"){
    U start=now+(c.write?3:4)*1000,end=start+2000;
    schedule(start,[this,start,end]{observe(0,start,end,64);});
   }
   if(e.op=="DONE"){
    active.erase(e.id);--used;
    if(--c.parent->left==0)c.parent->done(c.parent->arrival,now);
   }
  }
  // Callbacks may enqueue children; never reserve their future completion.
  if(used)schedule(now+1000,[this,now]{tick(now+1000);});else running=false;
 }
public:
 BankAdapter(hbfsim::physical::hbm::HbmConfig config,U capacity,
  std::function<void(U,std::function<void()>)> s,std::function<void(U,U,U,U)> o)
  :address_capacity(config.capacity_bytes),limit(capacity),schedule(std::move(s)),observe(std::move(o)){if(!limit||!address_capacity)throw std::invalid_argument("zero capacity");}
 bool submit(U now,bool write,U address,U bytes,Done done){
  if(now<last||!bytes||address>=address_capacity||bytes>address_capacity-address)throw std::invalid_argument("invalid bank parent");
  U count=(bytes-1)/64+1+(address%64+(bytes-1)%64>=64);
  if(count>limit-used)return false;
  last=now;used+=count;auto p=std::make_shared<Parent>(Parent{now,count,std::move(done)});
  for(U pos=address,left=bytes;left;){U n=std::min(left,64-pos%64);waiting.push_back({++id,pos,write,p});pos+=n;left-=n;}
  if(!running){
   U start=now+1000;
   if(cycle){while(next_ps<start){controller.step(cycle++);next_ps+=1000;}start=next_ps;}
   running=true;schedule(start,[this,start]{tick(start);});
  }
  return true;
 }
 U resident_bursts()const{return used;}
};
