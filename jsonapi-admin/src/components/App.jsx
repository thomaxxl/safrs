import './style/bootstrapstyle.css'
import '../style/style.css'

import * as Param from '../Config'
import React, { Component } from 'react'
import {  Route, HashRouter as Router} from 'react-router-dom'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import HeaderNavContainer from './HeaderNavContainer'
import Home from './Home'
import ApiObjectContainer from './ApiObject/ApiObjectContainer'
import * as ObjectAction from '../action/ObjectAction'
import * as ModalAction from '../action/ModalAction'
import * as InputAction from '../action/InputAction'
import * as SpinnerAction from '../action/SpinnerAction'
import ItemInfo from './Common/ItemInfo'
import Admin from 'components/Admin/Admin'

function genCollectionRoute(key) {
    
    const mapStateToProps = state => ({
        objectKey: key,
        item: Param.APP[key],
        api_data: state.object,
        inputflag: state.inputReducer
    })
    
    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        modalaction: bindActionCreators(ModalAction,dispatch),
        inputaction: bindActionCreators(InputAction,dispatch),
        spinnerAction: bindActionCreators(SpinnerAction,dispatch)
        //formaction: bindActionCreators(FormAction,dispatch),
        //getRelationship: getRelationship
    })
    
    const Results = connect(mapStateToProps, mapDispatchToProps)(ApiObjectContainer)
    return <Route key={key}  path={Param.APP[key].path} component={Results} />
}

function genItemRoute(key) {

    const mapStateToProps = state => ({
        objectKey: key,
        api_data: state.object,
        item: Param.APP[key]
    })

    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        modalaction: bindActionCreators(ModalAction,dispatch)
    })

    const Results = connect(mapStateToProps, mapDispatchToProps)(ItemInfo)
    let path = `${Param.APP[key].path}/:itemId`
    return <Route sensitive key={path} path={path} component={Results}/>
}


class App extends Component {

    render() {
        const collectionRoutes = Object.keys(Param.APP).map((key) => [genItemRoute(key), genCollectionRoute(key)] )
        return <Router>
                  <div>
                      <HeaderNavContainer/>
                      {/* <Switch> */}
                          <Route exact path="/" component={Home} />
                          <Route sensitive key="100" path="/Admin" component={Admin}/>
                          {/* <Route path="/admin" component={Admin} /> */}
                          {collectionRoutes}
                      {/* </Switch> */}
                  </div>
                </Router>  
    }
}

export default App
