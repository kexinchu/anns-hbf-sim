#pragma once
#include "aou_hbf_wire.hpp"
#include <array>
#include <deque>
#include <stdexcept>
#include <algorithm>
namespace ucie {
// Decoded-event lifetime model, NOT a Format-6 / PCIe retry wire implementation.
// Frame contains only payload and the real 8-bit sequence number. crc_ok is a
// fault-injection outcome, not an identity field. No generation crosses the link.
struct Frame {unsigned seq; aou::Bytes payload; bool crc_ok=true; bool is_ack=false;};
struct Endpoint {
 enum State {Reset,Active,Retrain,LinkReset,Disabled,LinkError};
 State state=Reset; bool req=false,sts=false; unsigned raised=0;
 unsigned next=1,expected=1,last=255; bool seen_payload=false;
 std::deque<Frame> retry,tx,rx;
};
struct Pair {
 std::array<Endpoint,2> ep;
 std::array<std::deque<Frame>,2> flight;
 unsigned clock=0,accepted=0,dropped=0,crc_errors=0,duplicates=0,discarded=0;
 static constexpr unsigned capacity=8; // implementation capacity <= normative 127
 static unsigned next(unsigned n){return n==255?1:n+1;}
 Endpoint& at(unsigned e){if(e>1)throw std::invalid_argument("endpoint");return ep[e];}
 void tick(){++clock;}
 bool request(unsigned e,bool high){auto& p=at(e);
  if(high){if(p.req||p.sts||!(p.state==Endpoint::Reset||p.state==Endpoint::Retrain||p.state==Endpoint::Active))return false;p.req=true;p.raised=clock;}
  else {if(!p.req||!p.sts)return false;p.req=false;}
  return true;
 }
 bool acknowledge(unsigned e){auto&p=at(e);if(p.req==p.sts||(p.req&&clock<=p.raised))return false;p.sts=p.req;return true;}
 bool transition(unsigned e,unsigned s){auto&p=at(e);if(s>Endpoint::LinkError)return false;auto to=Endpoint::State(s);
  if(to==Endpoint::LinkError){p.state=to;return true;} // asynchronous exceptional entry
  if(to==Endpoint::Active){if(!(p.state==Endpoint::Reset||p.state==Endpoint::Retrain)||!p.req||!p.sts)return false;p.state=to;return true;}
  if(to==Endpoint::Reset)return false; // coordinated completion below, never local shortcut
  if(p.req||p.sts||!(p.state==Endpoint::Active||p.state==Endpoint::Retrain))return false;
  p.state=to;return true;
 }
 bool send(unsigned e,const aou::Bytes& bytes){auto&p=at(e);if(p.state!=Endpoint::Active||p.retry.size()>=capacity||p.tx.size()>=capacity)return false;
  Frame f{p.next,bytes};p.next=next(p.next);p.retry.push_back(f);p.tx.push_back(f);return true;
 }
 bool launch(unsigned e){auto&p=at(e);if(p.state!=Endpoint::Active||p.tx.empty()||flight[e].size()>=capacity)return false;flight[e].push_back(p.tx.front());p.tx.pop_front();return true;}
 // Physical flight is an owned, ordered FIFO. Reset never asserts it is empty:
 // every queued item must pass this operation, which gates/drops it explicitly.
 bool arrive(unsigned e,bool corrupt=false){at(e);if(flight[e].empty())return false;auto f=flight[e].front();auto&r=ep[1-e];
  bool gate=r.req&&r.sts&&(r.state==Endpoint::Reset||r.state==Endpoint::Retrain||r.state==Endpoint::Active);
  // A full holding FIFO stalls this modeled physical step without losing bytes.
  if(gate&&!corrupt&&f.crc_ok&&!f.is_ack&&f.seq==r.expected&&r.rx.size()>=capacity)return false;
  flight[e].pop_front();
  if(!gate){++dropped;return true;}
  if(corrupt||!f.crc_ok){++crc_errors;return true;}
  if(f.is_ack){ack(1-e,f.seq);return true;}
  if(!f.seq||f.seq>255){r.state=Endpoint::LinkError;return true;}
  if(f.seq!=r.expected){++duplicates;return true;} // bounded in-order fixture; no selective retry
  r.rx.push_back(f);r.seen_payload=true;r.last=f.seq;r.expected=next(f.seq);++accepted;return true;
 }
 // Decoded ACK control units share owned TX/flight queues; ACKs themselves
 // are not retained for replay. Real Format-6 multiplexing remains unmodeled.
 bool queue_ack(unsigned e){auto&p=at(e);if(p.state!=Endpoint::Active||!p.seen_payload||p.tx.size()>=capacity)return false;p.tx.push_back(Frame{p.last,{},true,true});return true;}
 bool ack(unsigned e,unsigned seq){auto&p=at(e);if(p.state!=Endpoint::Active||!seq||seq>255)return false;
  auto it=std::find_if(p.retry.begin(),p.retry.end(),[&](const auto&f){return f.seq==seq;});if(it==p.retry.end())return false;
  p.retry.erase(p.retry.begin(),++it);return true;
 }
 // Explicit replay request of all unacknowledged flits; schedule/timeout policy
 // and Ack/Nak wire parsing are intentionally outside this bounded model.
 bool replay(unsigned e){auto&p=at(e);if(p.state!=Endpoint::Active||p.retry.empty()||p.tx.size()+p.retry.size()>capacity)return false;for(const auto&f:p.retry)p.tx.push_back(f);return true;}
 bool consume(unsigned e,aou::Bytes& out){auto&p=at(e);if(p.state!=Endpoint::Active||!p.req||!p.sts||p.rx.empty())return false;out=p.rx.front().payload;p.rx.pop_front();return true;}
 bool cleanup(unsigned e){auto&p=at(e);if(p.req||p.sts||!(p.state==Endpoint::LinkReset||p.state==Endpoint::Disabled))return false;
  // Incremental, auditable destruction: no assumed flush and no global drain.
  for(auto*q:{&p.tx,&p.retry,&p.rx})if(!q->empty()){q->pop_front();++discarded;return true;}return false;
 }
 bool reset_exit(){for(const auto&p:ep)if((p.state!=Endpoint::LinkReset&&p.state!=Endpoint::Disabled)||p.req||p.sts||!p.tx.empty()||!p.retry.empty()||!p.rx.empty())return false;
  if(!flight[0].empty()||!flight[1].empty())return false;
  for(auto&p:ep){p.state=Endpoint::Reset;p.next=p.expected=1;p.last=255;p.seen_payload=false;}return true;
 }
};
}
