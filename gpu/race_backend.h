#pragma once
extern "C" void race_init();
extern "C" void race_fill(int frame,int value);
extern "C" void race_start(int frame,bool held);
extern "C" bool race_ready(int frame);
extern "C" void race_open(int frame);
extern "C" void race_result(int frame,long long* scores);
extern "C" void race_copy(int frame,int* data);
extern "C" void race_close();
