/* Allocates new memory to hold the numBits specified and fills the allocated
    memory with the numBits specified starting from the startBit of the oldKey
    array of bytes. */
char *createStem(char *oldKey, unsigned int startBit, unsigned int numBits);

#define BITS_PER_BYTE 8


/*
    Instance  first invorking:
        *oldkey = "apple"
        startBit = 0
        numBits = 40
        *newStem = "apple"

    second invorking:
        *oldkey = 'appe'
        startBit = 3*8 + ?(查表)
        numBits =   ? (查表)
        *newStem = “e” ， is this correct?

*/

char *createStem(char *oldKey, unsigned int startBit, unsigned int numBits){
    assert(numBits > 0 && startBit >= 0 && oldKey);

    int extraBytes = 0;
    if((numBits % BITS_PER_BYTE) > 0){
        // 如果传入的 numBits 不是刚好一个字节， 则占有一个字节的空间。
        extraBytes = 1;
    }
    /* 我认为这样写，更容易理解
    int extraBytes = 1;
    if (numBits % BITS_PER_BYTE == 0 ){
        //  如果刚好是 8 bits, 16 bits, 24 bits, 则不需要额外的 字节计数。
        extraBytes = 0;
    }
    */




    // count from 1. not 0.
    int totalBytes = (numBits / BITS_PER_BYTE) + extraBytes;
    
    //申请  字符串 空间，
    char *newStem = malloc(sizeof(char) * totalBytes);
    assert(newStem);
    
    // 初始化该空间
    for(unsigned int i = 0; i < totalBytes; i++){
        newStem[i] = 0;
    }


    for(unsigned int i = 0; i < numBits; i++){
        // indexFromLeft, range is [0..7]， 从左向右排列。
        unsigned int indexFromLeft = i % BITS_PER_BYTE;
        
        // offset,  range is [0..7],   从右向左排列。  
        unsigned int offset = (BITS_PER_BYTE - indexFromLeft - 1) % BITS_PER_BYTE;
        
        // 有且仅有一个 bit 的 value == 0
        unsigned int bitMaskForPosition = 1 << offset;

        // 这里 startBit 必须 ==0 ,  am I right?  IMPORTANT HERE  !!!
        // ex. "apple", 
        unsigned int bitValueAtPosition = getBit(oldKey, startBit + i);

        // 如果上面的  startBit !=0,   
        unsigned int byteInNewStem = i / BITS_PER_BYTE;
 
        // 一个 bit, 又一个 bit 来赋值。
        newStem[byteInNewStem] |= bitMaskForPosition * bitValueAtPosition;
    }
    // 返回新分配的内存指针， 注意：is in heap, NOT in stack. 
    return newStem;
}