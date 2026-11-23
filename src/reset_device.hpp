#pragma once
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include "hbf_eventlab/runtime/block_replacement.hpp"
#include "hbf_eventlab/runtime/nand_media_state.hpp"
#include <map>
#include <set>
#include <vector>
#include <string>
// Device endpoint, independent of VersionedPages. Synthetic ticks, not silicon timing.
// Identity zone mapping; actual replacement translation resolves the physical target.
class ResetDevice {
 using G=hbf_eventlab::Geometry;
 using P=hbf_eventlab::PhysicalNandAddress;
 using B=hbf_eventlab::PhysicalBlockKey;
 struct Channel {bool power=false,link=false,en=false;unsigned type=0;std::uint64_t epoch=0,boot=0;};
 struct Operation {P physical;std::uint64_t value,due,epoch,die_epoch;bool live=true;};
 G g;hbf_eventlab::ReferenceAddressLayout layout;hbf_eventlab::RoundRobinInterleaver interleave;
 hbf_eventlab::BlockReplacement replacement;hbf_eventlab::NandMediaState media;
 std::vector<Channel> channels;std::map<std::pair<unsigned,unsigned>,std::uint64_t> die_boot;
 std::map<std::uint64_t,Operation> operations;std::set<B> uncertain;
 struct Response {unsigned channel,die;std::uint64_t epoch,die_epoch;};
 std::map<std::uint64_t,Response> responses;
 std::map<std::pair<unsigned,unsigned>,std::uint64_t> die_epochs;
 std::map<B,unsigned> next_page;
 std::uint64_t tick=0;
 Channel& channel(unsigned c){if(c>=channels.size())throw std::invalid_argument("channel");return channels[c];}
 void interrupt(unsigned c,int die){for(auto&[id,o]:operations)if(o.live&&o.physical.channel==c&&(die<0||o.physical.die==unsigned(die))){uncertain.insert(hbf_eventlab::block_of(o.physical));o.live=false;}}
public:
 explicit ResetDevice(G geometry={2,2,2,4,2,1},std::uint64_t stripe=64):g(geometry),layout(g),interleave(hbf_eventlab::GlobalByteAddress{4096},g.host_channels,g.channel_bytes(),stripe),replacement(g),media(g),channels(g.host_channels){}
 P map(std::uint64_t address)const{auto a=interleave.map(hbf_eventlab::GlobalByteAddress{address});return replacement.translate(layout.decode({a.channel,hbf_eventlab::MediaDlu{a.local.value/4096},unsigned(a.local.value%4096)}));}
 bool die_ready(unsigned c,unsigned d){auto&ch=channel(c);if(d>=g.dies_per_channel)throw std::invalid_argument("die");return ch.power&&ch.link&&(!die_boot.count({c,d})||die_boot.at({c,d})<=tick);}
 void power_on(){for(auto&ch:channels){if(ch.power)throw std::invalid_argument("already powered");}for(auto&ch:channels){ch.power=true;ch.link=false;ch.en=false;ch.boot=tick+5;++ch.epoch;}}
 void power_loss(){for(unsigned c=0;c<channels.size();c++){interrupt(c,-1);auto&ch=channels[c];ch.power=false;ch.link=false;ch.en=false;++ch.epoch;ch.boot=0;}die_boot.clear();}
 std::uint32_t csr_read(unsigned c,unsigned offset){auto&ch=channel(c);if(!ch.power)throw std::invalid_argument("unpowered CSR");if(offset==0x0c)return ch.en;if(offset==0x10)return ch.link?1:0;if(offset==0x14)return ch.type;throw std::invalid_argument("unsupported CSR");}
 std::string csr_write(unsigned c,unsigned offset,std::uint32_t value){auto&ch=channel(c);if(!ch.power)throw std::invalid_argument("unpowered CSR");
  if(offset==0x0c){if(value>1)throw std::invalid_argument("unsupported BUCC fields");ch.en=value;return "enabled";}
  if(offset!=0x14)throw std::invalid_argument("read-only or unsupported CSR");
  if((value>>8)!=0x484246)return "ignored";
  if((value&0xfc)||(value&3)==3)throw std::invalid_argument("reserved reset field");
  for(auto&[id,o]:operations)if(o.live&&o.physical.channel==c)uncertain.insert(hbf_eventlab::block_of(o.physical));
  ch.type=value&3;++ch.epoch;ch.link=false;ch.boot=tick+5;
  if(ch.type==2){interrupt(c,-1);ch.en=false;}
  return "reset";
 }
 // Fault interface: physically addressed die recovery, NOT a fabricated OCP CSR.
 void die_reset(unsigned c,unsigned d){auto&ch=channel(c);if(!ch.power||d>=g.dies_per_channel)throw std::invalid_argument("die reset");interrupt(c,int(d));++die_epochs[{c,d}];die_boot[{c,d}]=tick+5;}
 std::string program(std::uint64_t id,std::uint64_t address,std::uint64_t value){
  auto p=map(address);auto&ch=channel(p.channel);if(operations.count(id))throw std::invalid_argument("reused ID");
  if(!ch.en||!die_ready(p.channel,p.die))return "blocked";
  if(p.byte_offset)throw std::invalid_argument("page base");
  if(uncertain.count(hbf_eventlab::block_of(p)))return "unknown";
  for(auto&[i,o]:operations)if(o.live&&hbf_eventlab::block_of(o.physical)==hbf_eventlab::block_of(p))return "busy";
  if(p.page!=next_page[hbf_eventlab::block_of(p)])return "order";
  operations.emplace(id,Operation{p,value,tick+10,ch.epoch,die_epochs[{p.channel,p.die}]});return "accepted";
 }
 std::pair<std::string,std::uint64_t> read(std::uint64_t address){auto p=map(address);if(!channel(p.channel).en||!die_ready(p.channel,p.die))return {"blocked",0};if(uncertain.count(hbf_eventlab::block_of(p)))return {"unknown",0};auto data=media.read(p);if(!data)return {"erased",0};return {"known",data->at(p.byte_offset/64).value};}
 void erase(std::uint64_t address){auto p=map(address);if(!channel(p.channel).en||!die_ready(p.channel,p.die))throw std::invalid_argument("erase blocked");for(auto&[i,o]:operations)if(o.live&&hbf_eventlab::block_of(o.physical)==hbf_eventlab::block_of(p))throw std::invalid_argument("erase in flight");media.erase(hbf_eventlab::block_of(p));uncertain.erase(hbf_eventlab::block_of(p));next_page[hbf_eventlab::block_of(p)]=0;}
 void replace(std::uint64_t address){auto a=interleave.map(hbf_eventlab::GlobalByteAddress{address});auto slot=layout.decode({a.channel,hbf_eventlab::MediaDlu{a.local.value/4096},unsigned(a.local.value%4096)});auto p=replacement.translate(slot);
  for(auto&[i,o]:operations)if(o.live&&hbf_eventlab::block_of(o.physical)==hbf_eventlab::block_of(p))throw std::invalid_argument("replace in flight");
  if(replacement.replace_failed(hbf_eventlab::block_of(slot),[]{})!=hbf_eventlab::ReplacementResult::Applied)throw std::invalid_argument("no spare");media.mark_unusable(hbf_eventlab::block_of(p));}
 std::string deliver(std::uint64_t id){auto it=responses.find(id);if(it==responses.end())return "absent";auto r=it->second;responses.erase(it);return channel(r.channel).power&&channel(r.channel).epoch==r.epoch&&die_epochs[{r.channel,r.die}]==r.die_epoch?"success":"stale";}
 void advance(std::uint64_t to){if(to<tick)throw std::invalid_argument("time reversal");tick=to;
  for(auto&ch:channels)if(ch.power&&ch.boot&&ch.boot<=tick){ch.link=true;ch.boot=0;}
  for(auto&[id,o]:operations)if(o.live&&o.due<=tick){hbf_eventlab::PageData data;data.fill(hbf_eventlab::DataToken{o.value});media.program(o.physical,data);++next_page[hbf_eventlab::block_of(o.physical)];o.live=false;responses.emplace(id,Response{o.physical.channel,o.physical.die,o.epoch,o.die_epoch});}
 }
};
