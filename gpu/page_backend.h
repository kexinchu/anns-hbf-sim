#pragma once
extern "C" void cuda_pages_init();
extern "C" void cuda_page_fill(int frame,const void* bytes);
extern "C" void cuda_page_score(int frame,const int* query,long long* scores);
extern "C" void cuda_pages_close();
extern "C" void cuda_page_readback(int frame,void* bytes);
