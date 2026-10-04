package com.halo.decomp;

/** Run with the production MotionAimMath.java and java -ea. No Android stubs. */
class MotionAimMathTest {
    private static void close(float actual,float expected,float epsilon) {
        if(Math.abs(actual-expected)>epsilon)
            throw new AssertionError(actual+" != "+expected);
    }
    private static float integrate(int hz,float gain) {
        MotionAimMath math=new MotionAimMath();float sum=0;
        long time=1_000_000_000L,step=1_000_000_000L/hz;
        math.sample(time,0,0,1,0,gain);
        for(int i=0;i<hz;i++) {
            time+=step;math.sample(time,0,0,1,0,gain);sum+=math.yaw;
        }
        return sum;
    }
    public static void main(String[] args) {
        /* Equivalent physical movements in all four display orientations. */
        float[][] axes={{1,2},{2,-1},{-1,-2},{-2,1}};
        float yaw=0,pitch=0;
        for(int rotation=0;rotation<4;rotation++) {
            MotionAimMath math=new MotionAimMath();long time=1_000_000_000L;
            assert !math.sample(time,rotation,axes[rotation][0],axes[rotation][1],0,1);
            for(int i=0;i<100;i++) {
                time+=10_000_000L;math.sample(time,rotation,axes[rotation][0],axes[rotation][1],0,1);
            }
            if(rotation==0){yaw=math.yaw;pitch=math.pitch;}
            else{close(math.yaw,yaw,1e-6f);close(math.pitch,pitch,1e-6f);}
            assert math.yaw>0 && math.pitch>0;
        }
        close(integrate(50,1),integrate(100,1),.012f);
        close(integrate(10,1),integrate(100,1),.03f); /* Slower handheld gyro still moves. */
        close(integrate(100,2),integrate(100,1)*2,1e-5f);
        close(integrate(100,.25f),integrate(100,1)*.25f,1e-5f);
        MotionAimMath math=new MotionAimMath();long time=1_000_000_000L;
        math.sample(time,0,0,0,0,1);
        assert !math.sample(time+=10_000_000L,0,.004f,-.004f,0,1);
        assert !math.sample(time+=400_000_000L,0,1,1,0,1); /* Gap cannot jump. */
        assert !math.sample(time+=10_000_000L,1,1,1,0,1); /* Rotation cannot jump. */
        assert !math.sample(time+=10_000_000L,1,Float.NaN,1,0,1);
        assert !math.sample(time+=10_000_000L,1,1,1,Float.POSITIVE_INFINITY,1);
        assert !math.sample(time+=10_000_000L,1,99,1,0,1);
        math.reset();
        assert !math.sample(time,0,1,1,0,1);
        assert !math.sample(time-1,0,1,1,0,1);
        math.reset();
        math.sample(time,0,25,25,0,2);
        assert math.sample(time+50_000_000L,0,25,25,0,2);
        assert math.yaw<=.12f && math.pitch<=.12f;
        System.out.println("Gyro math: display rotations, rate independence, sensitivity, noise, gaps, invalid samples and reset passed.");
    }
}
