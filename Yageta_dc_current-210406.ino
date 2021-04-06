// 端子定義
const int arefPin = 0;
const int voltagePin = 1;
const int currentPin = 2;

// 通信設定
#define SER_SPEED  (115200)

// 商用電源周波数
// NIFS は(60)、東京は（50）
#define POWER_FREQ        (60)

// １サイクルあたりのサンプル数
#define NUMBER_OF_SAMPLES (24)

// サンプリング間隔(マイクロ秒 = 1000000)
#define SAMPLING_PERIOD   (1000000/(POWER_FREQ * NUMBER_OF_SAMPLES))

// デバッグ用
#define DEBUG 0

// 実効電圧、実効電流、有効電力
// rms = 実効値
float Vrms;
float Irms;
float Watt;

// サンプリング用バッファ
int VASamples[NUMBER_OF_SAMPLES*4];

void calcWatt(void)
{
#define kVT    (88.99)    // 実測にもとづく係数, V=Voltage
#define kCT    (100.0 * 0.99 / 3000.0) // R * 係数 / 巻き数, 100(Ohm), C=Current

  unsigned long t1,t2;
  int i,r,v1,a1,a2,v2;

  t1 = micros();

  // １サイクル分のAD値をサンプリング
  for(i=0; i<NUMBER_OF_SAMPLES; i++){

    r = analogRead(arefPin);
    v1 = analogRead(voltagePin);
    a1 = analogRead(currentPin);
    a2 = analogRead(currentPin);
    v2 = analogRead(voltagePin);

    VASamples[(i*4)+0] = v1 - r;
    VASamples[(i*4)+1] = a1 - r;
    VASamples[(i*4)+2] = a2 - r;
    VASamples[(i*4)+3] = v2 - r;

    do {
      t2 = micros();
    } 
    while((t2 - t1) < SAMPLING_PERIOD);
    t1 += SAMPLING_PERIOD;
  }

  // １サイクル分の電圧と電流、電力を加算
  Vrms = 0;
  Irms = 0;
  Watt = 0;

  for(i=0; i<NUMBER_OF_SAMPLES; i++){
    v1 = VASamples[(i*4)+0];
    a1 = VASamples[(i*4)+1];
    a2 = VASamples[(i*4)+2];
    v2 = VASamples[(i*4)+3];

    float vv = ((((v1+v2)/2) * 5.0) / 1024) * kVT;
    float aa = ((((a1+a2)/2) * 5.0) / 1024) / kCT;

    Vrms += vv * vv;
    Irms += aa * aa;
    Watt += vv * aa;
  }

  // 2乗平均平方根(rms)を求める
  Vrms = sqrt(Vrms / NUMBER_OF_SAMPLES);
  Irms = sqrt(Irms / NUMBER_OF_SAMPLES);

  // 平均電力を求める
  Watt = Watt / NUMBER_OF_SAMPLES;
}

float watt_hour;
float vrms_sum;
float irms_sum;
float watt_sum;
int watt_samples;
unsigned long last_update;

void setup()
{
  Serial.begin(SER_SPEED);
  watt_hour     = 0;
  vrms_sum      = 0;
  irms_sum      = 0;
  watt_sum      = 0;
  watt_samples  = 0;
  last_update   = millis();
}

void loop()
{
  unsigned long curr_time;

  // 電力を計算
  calcWatt();

  // 1秒分加算する
  vrms_sum += Vrms;
  irms_sum += Irms;
  watt_sum += Watt;
  watt_samples++;

  // １秒経過したらシリアルに出力
  curr_time = millis();
  if( (curr_time - last_update) > 1000 ){
#if DEBUG
    for(int i=0; i<NUMBER_OF_SAMPLES; i++){
      Serial.print(VASamples[(i*4)+0]);
      Serial.print('\t');
      Serial.println(VASamples[(i*4)+1]);
      Serial.print(VASamples[(i*4)+3]);
      Serial.print('\t');
      Serial.println(VASamples[(i*4)+2]);
    }
#endif
    vrms_sum /= watt_samples;
    irms_sum /= watt_samples;
    watt_sum /= watt_samples;

    Serial.print(vrms_sum);
//    Serial.print("Vrms, ");
    Serial.print(" ");
    
    Serial.print(irms_sum);
//    Serial.print("Irms, ");
    Serial.print(" ");
    
//    Serial.print(vrms_sum * irms_sum);
//    Serial.print("VA, ");

    Serial.println(watt_sum);
//    Serial.print("W, ");

    // 力率 = 有効電力 / 皮相電力
//    Serial.print((watt_sum * 100) / (vrms_sum * irms_sum));
//    Serial.print("%, ");

    // 積算Whを求める
//    watt_hour += watt_sum / 3600.0;
//    Serial.print(watt_hour);
//    Serial.println("Wh");

    watt_samples = 0;
    vrms_sum = irms_sum = watt_sum = 0;

    last_update = curr_time;
  }
}
