#pragma once
#include "aou_hbf_wire.hpp"
#include <deque>
#include <map>
#include <set>
#include <functional>
namespace aou {
// Decoded Chapter 8 control events, not a claim of full activation/flit codec.
struct Link {
 enum State{Disabled,Activate,Enabled,Deactivate,Error};State state=Disabled;
 bool req_sent=false,req_seen=false,ack_sent=false,ack_seen=false;
 unsigned credits=0;std::deque<Bytes> tx,rx;
 std::set<unsigned> live,retired;std::map<unsigned,std::function<void(const Message&)>> callbacks;
 unsigned time_sync=0,msg_count=0;
 static constexpr unsigned capacity=8;
 void activate_request(bool outgoing){if(state!=Disabled&&state!=Activate){fail();return;}state=Activate;(outgoing?req_sent:req_seen)=true;}
 void activate_ack(bool outgoing){if(state!=Activate||!req_sent||!req_seen){fail();return;}(outgoing?ack_sent:ack_seen)=true;if(ack_sent&&ack_seen)state=Enabled;}
 void grant(unsigned n){if(state!=Enabled&&!(state==Activate&&ack_seen))throw std::logic_error("credit state");credits=n>capacity-credits?capacity:credits+n;}
 bool send(Message m,std::function<void(const Message&)> completion){
  if(state!=Enabled||!credits||tx.size()>=capacity||live.count(m.id)||retired.count(m.id))return false;
  if(m.kind!=2||m.rp!=0)throw std::invalid_argument("read-only single RP fixture");
  auto bytes=encode(m);live.insert(m.id);callbacks.emplace(m.id,std::move(completion));--credits;tx.push_back(std::move(bytes));return true;
 }
 bool receive(const Bytes& bytes){if(state==Error||state==Disabled||state==Activate)return false;
  auto m=decode(bytes);if(m.rp)throw std::invalid_argument("unsupported RP");
  if(m.kind==0){time_sync=m.sync;msg_count=m.count;return true;} // observations, NOT identity
  if(m.kind!=4||!live.count(m.id))return false;
  auto cb=std::move(callbacks.at(m.id));callbacks.erase(m.id);live.erase(m.id);retired.insert(m.id);cb(m);return true;
 }
 void fail(){state=Error;credits=0;}
 // Implementation-defined local teardown; owned FIFOs are physically discarded.
 // This cannot certify absence of a packet stored in an unmodeled lower layer.
 void teardown(){if(state!=Error)throw std::logic_error("teardown state");tx.clear();rx.clear();live.clear();callbacks.clear();state=Disabled;credits=0;req_sent=req_seen=ack_sent=ack_seen=false;}
 bool deactivate(){if(state!=Enabled||!live.empty()||!tx.empty()||!rx.empty())return false;state=Deactivate;return true;}
 // Reuse is conservatively allowed only across a fully closed local transport.
 void disabled_ack(){if(state!=Deactivate)throw std::logic_error("deactivate ack state");state=Disabled;credits=0;req_sent=req_seen=ack_sent=ack_seen=false;}
 void release_ids(){if(state!=Disabled||!live.empty()||!tx.empty()||!rx.empty())throw std::logic_error("ID release before transport closure");retired.clear();}
};
}
