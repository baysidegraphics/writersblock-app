"""Match Kokoro's speed input to the loaded ONNX model, without changing the SDK."""
class ModelInputs:
    def __init__(self,session):
        self._session=session
        self._speed=next((item.type for item in session.get_inputs() if item.name=='speed'),None)
    def __getattr__(self,name):return getattr(self._session,name)
    def run(self,output_names,input_feed,*args,**kwargs):
        import numpy as np
        types={'tensor(float)':np.float32,'tensor(double)':np.float64,'tensor(int32)':np.int32,'tensor(int64)':np.int64}
        if 'speed' in input_feed and self._speed in types:
            input_feed={**input_feed,'speed':np.asarray(input_feed['speed'],dtype=types[self._speed])}
        return self._session.run(output_names,input_feed,*args,**kwargs)
